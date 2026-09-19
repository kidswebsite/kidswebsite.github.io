# Three Kids, One City

A small public website: a landing page and one page per child. Each page
rebuilds itself when that child emails the site mailbox; the text and photos in
the email become a new post.

Everything is free: GitHub Pages for hosting, GitHub Actions for the scheduled
check, and an ordinary Gmail account for the inbox. No domain, no server.

```
index.html                          landing page            ← generated
olivia.html  treevor.html  jamie.html                       ← generated
site.json                           names, colours, tagline — edit this
content/*.json                      the posts (written by the email script)
media/<name>/                       photos from emails
assets/style.css                    styling
assets/edinburgh.jpg                hero photo (Strevo, CC BY 2.0)
scripts/fetch_mail.py               reads the mailbox, writes posts
scripts/build.py                    turns content/*.json into HTML
.github/workflows/update-site.yml   runs both every 15 minutes, then deploys
```

Never edit the `.html` files by hand — they are overwritten on every build.
Edit `site.json` or `assets/style.css` and run `python3 scripts/build.py`.

## Privacy

The pages use pen names only. No real name, email address or school appears in
this repository, in the generated pages, or in the Actions logs — the logs
print a slug and a sender's domain, never a name, an address or a subject line.

Photos are re-encoded before publishing, which strips EXIF: no GPS
coordinates, no camera serial, no original timestamp. An image that cannot be
re-encoded is dropped rather than published as sent.

The real addresses live only in the `SENDER_MAP` repository secret, which is
write-only once set and is never printed.

Anything posted is still visible to everyone and to search engines. Worth
asking the children to avoid friends' names, the school name, uniforms and
house fronts.

## Setup

### 1. The mailbox

A dedicated Gmail account, nothing personal in it — the script reads the whole
inbox. Turn on 2-Step Verification, then create an **App password** at
`myaccount.google.com/apppasswords` and keep the 16-character string.

### 2. Push

```bash
git init -b main
git add .
git commit -m "Site"
git remote add origin https://github.com/<account>/<repo>.git
git push -u origin main
```

### 3. Pages

Repository → **Settings → Pages → Build and deployment → Source: GitHub Actions**.

### 4. Secrets

Repository → **Settings → Secrets and variables → Actions → New repository secret**:

| Name | Value |
|---|---|
| `IMAP_HOST` | `imap.gmail.com` |
| `IMAP_USER` | the site mailbox address |
| `IMAP_PASSWORD` | the 16-character app password |
| `SENDER_MAP` | `<child1>@gmail.com=olivia,<child2>@gmail.com=treevor,<child3>@gmail.com=jamie` |

`SENDER_MAP` is the whole security model: **one sender, one page**. A message is
published only if its `From:` address appears there, and it always goes to that
sender's own page — a child cannot post to a sibling's page, and mail from
anyone else is ignored and left unread. The addresses live in a secret rather
than in the repository so they are never published.

### 5. Run it

Actions tab → *Update site from email* → **Run workflow**. After that it runs
by itself every 15 minutes. GitHub can delay scheduled runs when busy, so a gap
of half an hour now and then is normal.

## How to post

Email the site mailbox from the address registered in `SENDER_MAP`. The subject
becomes the post title, the body the text, and attached or inline photos the
gallery. Quoted replies and "Sent from my iPhone" are trimmed; photos are
shrunk to 1600 px.

## Removing a post

Edit the relevant `content/<name>.json`, delete the entry and its files under
`media/`, commit and push. The site rebuilds on push.

## Local preview

```bash
python3 scripts/build.py
python3 -m http.server 8000   # then open http://localhost:8000
```
