#!/usr/bin/env python3
"""Pull new emails from the site mailbox and turn them into posts.

One sender, one page. A message is published only if its From: address is in
SENDER_MAP, and it always goes to that sender's own page. Anything else is
left unread and ignored, so a stranger who learns the site address cannot put
anything on a child's page.

Environment variables (set as GitHub Actions secrets):
  IMAP_HOST      e.g. imap.gmail.com
  IMAP_USER      the site mailbox address
  IMAP_PASSWORD  a Gmail app password (NOT the account password)
  SENDER_MAP     address=slug pairs, comma separated, e.g.
                 "someone@example.com=olivia,other@example.com=treevor"
  IMAP_FOLDER    optional, default INBOX

The subject becomes the post title, the body the text, and attached or inline
photos the gallery.
"""
import os, re, ssl, json, email, imaplib, hashlib, pathlib, mimetypes, datetime
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime, getaddresses

try:                                  # iPhone photos arrive as HEIC
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    print("warning: pillow-heif missing, HEIC photos will be dropped")

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
KIDS = {k["slug"]: k for k in SITE["kids"]}
MEDIA = ROOT / "media"
MAX_PX = 1600

HOST = os.environ["IMAP_HOST"]
USER = os.environ["IMAP_USER"]
PASSWORD = os.environ["IMAP_PASSWORD"]
FOLDER = os.environ.get("IMAP_FOLDER", "INBOX")


def parse_sender_map(raw):
    mapping = {}
    for pair in (raw or "").split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            raise SystemExit(f"SENDER_MAP entry {pair!r} is not address=slug")
        addr, slug = (p.strip() for p in pair.split("=", 1))
        if slug not in KIDS:
            raise SystemExit(f"SENDER_MAP: {slug!r} is not a slug in site.json")
        mapping[addr.lower()] = slug
    if not mapping:
        raise SystemExit("SENDER_MAP is empty — refusing to publish anything.")
    return mapping


SENDERS = parse_sender_map(os.environ.get("SENDER_MAP", ""))


def dec(value):
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def strip_html(raw):
    raw = re.sub(r"(?is)<(script|style).*?</\1>", "", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?i)</p>", "\n\n", raw)
    raw = re.sub(r"<[^>]+>", "", raw)
    import html as _h
    return _h.unescape(raw)


def clean_body(text):
    lines = []
    for line in (text or "").replace("\r\n", "\n").split("\n"):
        if re.match(r"^\s*(On .{10,80}wrote:|-{2,}\s*Original Message|Sent from my )", line):
            break
        if line.strip().startswith(">"):
            continue
        line = re.sub(r"\[image:[^\]]*\]", "", line)
        lines.append(line.rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines).strip())


def extract(msg):
    text, htmlpart, images = "", "", []
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        ctype = part.get_content_type()
        disp = (part.get("Content-Disposition") or "").lower()
        if ctype == "text/plain" and "attachment" not in disp and not text:
            text = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
        elif ctype == "text/html" and "attachment" not in disp and not htmlpart:
            htmlpart = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
        elif part.get_content_maintype() == "image":
            payload = part.get_payload(decode=True)
            if payload:
                images.append((part.get_filename() or "", ctype, payload))
    return clean_body(text) or clean_body(strip_html(htmlpart)), images


def save_image(slug, post_id, index, filename, ctype, payload):
    ext = pathlib.Path(filename).suffix.lower() or mimetypes.guess_extension(ctype) or ".jpg"
    if ext in (".jpe", ".jpeg", ".heic", ".heif"):
        ext = ".jpg"               # HEIC is re-encoded to JPEG below
    if ext not in (".jpg", ".png", ".gif", ".webp"):
        ext = ".jpg"
    folder = MEDIA / slug
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{post_id}-{index}{ext}"
    # Re-encode through Pillow so the file that ships carries no EXIF: no GPS
    # coordinates, no camera serial, no original timestamp. If that cannot be
    # done, drop the image rather than publish the original.
    try:
        import io
        from PIL import Image, ImageOps
        with Image.open(io.BytesIO(payload)) as src:
            im = ImageOps.exif_transpose(src)
            if max(im.size) > MAX_PX:
                im.thumbnail((MAX_PX, MAX_PX), Image.LANCZOS)
            if im.mode in ("RGBA", "P") and ext == ".jpg":
                im = im.convert("RGB")
            if im.mode not in ("RGB", "L") and ext == ".jpg":
                im = im.convert("RGB")
            clean = Image.new(im.mode, im.size)
            clean.putdata(list(im.getdata()))
            clean.save(path, quality=85, optimize=True)
    except Exception as exc:
        print(f"      image dropped, could not be re-encoded: {type(exc).__name__}")
        return None
    return f"media/{slug}/{path.name}"


def add_post(slug, post):
    f = ROOT / "content" / f"{slug}.json"
    data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"posts": []}
    if any(p.get("id") == post["id"] for p in data["posts"]):
        return False
    data["posts"].append(post)
    f.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def main():
    imap = imaplib.IMAP4_SSL(HOST, ssl_context=ssl.create_default_context())
    imap.login(USER, PASSWORD)
    imap.select(FOLDER)
    uids = imap.search(None, "UNSEEN")[1][0].split()
    print(f"{len(uids)} unread message(s)")
    added = ignored = 0

    for uid in uids:
        msg = email.message_from_bytes(imap.fetch(uid, "(BODY.PEEK[])")[1][0][1])
        sender = (getaddresses(msg.get_all("from", [])) or [("", "")])[0][1].lower().strip()
        subject = dec(msg.get("subject", "")).strip()

        slug = SENDERS.get(sender)
        if not slug:
            # Redacted: these logs are public on a public repository.
            domain = sender.split("@")[-1] if "@" in sender else "?"
            print(f"  ignored, sender not on the list (@{domain})")
            ignored += 1
            continue

        try:
            date = parsedate_to_datetime(msg.get("date"))
        except Exception:
            date = datetime.datetime.now(datetime.timezone.utc)
        if date.tzinfo is None:
            date = date.replace(tzinfo=datetime.timezone.utc)

        mid = msg.get("message-id") or f"{sender}{subject}{date}"
        post_id = date.strftime("%Y%m%d") + "-" + hashlib.sha1(mid.encode()).hexdigest()[:8]

        body, images = extract(msg)
        saved = [{"src": src, "alt": ""} for src in
                 (save_image(slug, post_id, i + 1, *img) for i, img in enumerate(images))
                 if src]

        if not body and not saved:
            print(f"  skipped, {slug}: nothing in it")
            imap.store(uid, "+FLAGS", "\\Seen")
            continue

        if add_post(slug, {"id": post_id, "date": date.isoformat(), "title": subject,
                           "body": body, "images": saved}):
            added += 1
            print(f"  + {slug}: post added, {len(saved)} image(s)")
        imap.store(uid, "+FLAGS", "\\Seen")

    imap.close()
    imap.logout()
    print(f"{added} new post(s), {ignored} ignored")


if __name__ == "__main__":
    main()
