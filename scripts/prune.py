#!/usr/bin/env python3
"""Keep the published site within its photo budget.

Photos are what fills the budget; words cost almost nothing. So when media/
grows past `media_budget_mb` in site.json, the oldest posts are *archived*:
their photo files are deleted and the post moves to that child's archive page,
keeping its title and text for good. Nothing anyone wrote is ever removed.

Archiving works on a date cutoff, so each child's main page holds the recent
posts and the archive holds everything older, in order.
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
MEDIA = ROOT / "media"
BUDGET = int(SITE.get("media_budget_mb", 300)) * 1024 * 1024


def media_bytes():
    return sum(f.stat().st_size for f in MEDIA.rglob("*") if f.is_file())


def load(slug):
    f = ROOT / "content" / f"{slug}.json"
    return f, (json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"posts": []})


def save(f, data):
    f.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def archive(post):
    """Delete this post's photo files; keep its words. Returns bytes freed."""
    freed = 0
    for img in post.get("images", []):
        path = ROOT / img["src"]
        if path.is_file():
            freed += path.stat().st_size
            path.unlink()
    if post.get("images"):
        post["had_images"] = post.get("had_images", 0) + len(post["images"])
    post["images"] = []
    post["archived"] = True
    return freed


def main():
    size = media_bytes()
    print(f"media: {size/1e6:.1f} MB of {BUDGET/1e6:.0f} MB budget")
    if size <= BUDGET:
        print("within budget, nothing to do")
        return

    # every post, oldest first, with the file it came from
    everything = []
    for kid in SITE["kids"]:
        f, data = load(kid["slug"])
        for post in data["posts"]:
            everything.append((post.get("date", ""), kid["slug"], f, data, post))
    everything.sort(key=lambda t: t[0])

    files, cutoff, archived = {}, None, 0
    for date, slug, f, data, post in everything:
        if size <= BUDGET:
            break
        if not post.get("archived"):
            size -= archive(post)
            archived += 1
        cutoff = date
        files[f] = data

    # everything older than the cutoff joins the archive, so the split is a
    # clean point in time rather than a scatter of individual posts
    if cutoff:
        for date, slug, f, data, post in everything:
            if date <= cutoff and not post.get("archived"):
                archive(post)
                archived += 1
                files[f] = data

    for f, data in files.items():
        save(f, data)

    print(f"archived {archived} post(s) up to {cutoff}; media now {media_bytes()/1e6:.1f} MB")
    print("note: git history still holds the deleted files — see scripts/compact_history.sh")


if __name__ == "__main__":
    main()
