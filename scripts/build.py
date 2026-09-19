#!/usr/bin/env python3
"""Regenerate the static site from site.json + content/<slug>.json."""
import json, html, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))


def esc(s):
    return html.escape(s or "", quote=True)


def head(title, extra_style=""):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="stylesheet" href="assets/style.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><text y='13' font-size='13'>&#127963;</text></svg>">
{extra_style}
</head>
<body>
"""


def build_index():
    cards = []
    for k in SITE["kids"]:
        posts = load_posts(k["slug"]) + load_posts(k["slug"], archived=True)
        posts.sort(key=lambda p: p.get("date", ""), reverse=True)
        n = len(posts)
        sub = "Nothing posted yet" if n == 0 else (f"{n} post" if n == 1 else f"{n} posts")
        if posts:
            sub += " · latest " + fmt_date(posts[0].get("date"), short=True)
        cards.append(f"""      <a class="card" style="--k:{esc(k['colour'])}" href="{esc(k['slug'])}.html">
        <div class="initial">{esc(k['short'][0])}</div>
        <h2>{esc(k['short'])}</h2>
        <p class="sub">{esc(k['name'])}</p>
        <p class="sub">{esc(sub)}</p>
        <div class="go">Open page &rarr;</div>
      </a>""")

    cr = SITE.get("photo_credit", {})
    out = head(SITE["title"]) + f"""<header class="hero">
  <img src="assets/edinburgh.jpg" alt="The Edinburgh skyline seen from Calton Hill">
  <div class="hero__veil"></div>
  <div class="hero__text"><div class="hero__inner">
    <h1>{esc(SITE['title'])}</h1>
    <p>{esc(SITE['tagline'])}</p>
  </div></div>
</header>
<p class="credit"><a href="{esc(cr.get('url',''))}">{esc(cr.get('text',''))}</a></p>

<main class="wrap">
  <nav class="names" aria-label="Choose a page">
{chr(10).join(cards)}
  </nav>
</main>

<footer>Pages update automatically when the kids email the site.</footer>
</body>
</html>
"""
    (ROOT / "index.html").write_text(out, encoding="utf-8")


def load_posts(slug, archived=False):
    f = ROOT / "content" / f"{slug}.json"
    if not f.exists():
        return []
    posts = [p for p in json.loads(f.read_text(encoding="utf-8")).get("posts", [])
             if bool(p.get("archived")) == archived]
    return sorted(posts, key=lambda p: p.get("date", ""), reverse=True)


def fmt_date(iso, short=False):
    if not iso:
        return ""
    try:
        d = datetime.datetime.fromisoformat(iso)
    except ValueError:
        return iso
    return d.strftime("%-d %b %Y") if short else d.strftime("%A %-d %B %Y, %H:%M")


def paras(text):
    blocks = [b.strip() for b in (text or "").split("\n\n") if b.strip()]
    return "\n".join(f"<p>{esc(b)}</p>" for b in blocks) or "<p></p>"


def render_posts(k, posts):
    items = []
    for p in posts:
        imgs = "".join(
            f'<img src="{esc(i["src"])}" alt="{esc(i.get("alt") or "Photo sent by " + k["short"])}" loading="lazy">'
            for i in p.get("images", [])
        )
        gallery = f'<div class="gallery">{imgs}</div>' if imgs else ""
        title = f"<h3>{esc(p['title'])}</h3>" if p.get("title") else ""
        n = p.get("had_images", 0)
        note = (f'<p class="dropped">{n} photo{"s" if n != 1 else ""} removed to save space</p>'
                if p.get("archived") and n else "")
        items.append(f"""    <li class="post">
      <time datetime="{esc(p.get('date',''))}">{esc(fmt_date(p.get('date')))}</time>
      {title}
      <div class="body">{paras(p.get('body'))}</div>
      {gallery}{note}
    </li>""")
    return items


def page(k, posts, *, archive):
    items = render_posts(k, posts)
    if items:
        body = "\n".join(items)
    elif archive:
        body = '<li class="empty">Nothing archived yet.</li>'
    else:
        body = '<li class="empty">Nothing here yet. Send an email to fill this page.</li>'

    if archive:
        title, sub = f"{k['short']} — earlier posts", "Earlier posts"
        back = f'<a class="back" href="{esc(k["slug"])}.html">&larr; {esc(k["short"])}</a>'
        link = ""
    else:
        title, sub = f"{k['short']} — {SITE['title']}", esc(SITE["city"])
        back = f'<a class="back" href="index.html">&larr; {esc(SITE["title"])}</a>'
        n = len(load_posts(k["slug"], archived=True))
        link = (f'<p class="more"><a href="{esc(k["slug"])}-archive.html">'
                f'Earlier posts ({n}) &rarr;</a></p>' if n else "")

    out = head(title) + f"""<div class="topbar"><div class="wrap">
  {back}
</div></div>

<main class="wrap" style="--k:{esc(k['colour'])}">
  <div class="kidhead">
    <h1>{esc(k['name'])}</h1>
    <p>{sub}</p>
  </div>
  <ul class="posts">
{body}
  </ul>
  {link}
</main>

<footer>Last built {datetime.datetime.now(datetime.timezone.utc).strftime('%-d %B %Y, %H:%M UTC')}</footer>
</body>
</html>
"""
    name = f"{k['slug']}-archive.html" if archive else f"{k['slug']}.html"
    (ROOT / name).write_text(out, encoding="utf-8")


def build_kid(k):
    page(k, load_posts(k["slug"]), archive=False)
    old = load_posts(k["slug"], archived=True)
    if old:
        page(k, old, archive=True)


if __name__ == "__main__":
    build_index()
    for kid in SITE["kids"]:
        build_kid(kid)
    print("Built index.html and", ", ".join(k["slug"] + ".html" for k in SITE["kids"]))
