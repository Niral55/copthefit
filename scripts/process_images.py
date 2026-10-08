"""Turn product photos into clean cutouts for slides and the site.

1. images/inbox/<find>-<slide>.<jpg|png|webp> (+ optional .json with {"product_url": ...})
   -> background removed -> images/cut/<find>-<slide>.png. The product link (if any) is saved on the item.
   The Chrome extension drops files here; you can also upload them on github.com.
2. Items that have a product_url but no image yet: fetch the page's main product image
   (og:image / JSON-LD), then cut it out the same way. One try per item; failures are listed.

Usage: python scripts/process_images.py [--no-fetch]
"""
import io
import json
import re
import sys
from datetime import date

from PIL import Image

from common import INBOX, CUT_DIR, load_fits, save_fits

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
EXTS = (".jpg", ".jpeg", ".png", ".webp", ".avif")
NAME = re.compile(r"^(\d{3})-(\d{1,2})$")
_session = None


def remove_bg(img):
    """Cut the product out. Images that already have transparency are only trimmed."""
    global _session
    img = img.convert("RGBA")
    alpha = img.getchannel("A")
    if alpha.getextrema()[0] < 250:  # already transparent somewhere
        out = img
    else:
        from rembg import remove, new_session
        if _session is None:
            _session = new_session("isnet-general-use")
        out = remove(img, session=_session)
    box = out.getchannel("A").point(lambda a: 255 if a > 12 else 0).getbbox()
    if box:
        out = out.crop(box)
    out.thumbnail((1400, 1400))
    pad = int(max(out.size) * 0.04)
    canvas = Image.new("RGBA", (out.width + pad * 2, out.height + pad * 2), (0, 0, 0, 0))
    canvas.paste(out, (pad, pad), out)
    return canvas


def find_item(doc, find, slide):
    for f in doc["fits"]:
        if f["find"] == find:
            for it in f["items"]:
                if it["slide"] == slide:
                    return it
    return None


def process_inbox(doc):
    done = 0
    for p in sorted(INBOX.iterdir()) if INBOX.exists() else []:
        if p.suffix.lower() not in EXTS:
            continue
        m = NAME.match(p.stem)
        if not m:
            print(f"skip {p.name}: name it <find>-<slide>, e.g. 003-2.jpg")
            continue
        find, slide = m.group(1), int(m.group(2))
        it = find_item(doc, find, slide)
        if not it:
            print(f"skip {p.name}: no item #{find} slide {slide} in data/fits.json")
            continue
        side = p.with_suffix(".json")
        if side.exists():
            meta = json.loads(side.read_text())
            if meta.get("product_url"):
                it["product_url"] = meta["product_url"]
            side.unlink()
        remove_bg(Image.open(p)).save(CUT_DIR / f"{find}-{slide}.png", optimize=True)
        it.pop("image_fetch", None)
        p.unlink()
        done += 1
        print(f"cut {find}-{slide}")
    return done


def page_image(url):
    import requests
    html = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}, timeout=25).text
    pats = [r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',
            r'"image"\s*:\s*\[?\s*"(https?://[^"]+)"']
    for pat in pats:
        m = re.search(pat, html, re.I)
        if m:
            from urllib.parse import urljoin
            return urljoin(url, m.group(1).replace("&amp;", "&"))
    return None


def fetch_missing(doc):
    import requests
    fails = []
    for f in doc["fits"]:
        if f["status"] not in ("approved", "review"):
            continue
        for it in f["items"]:
            key = f"{f['find']}-{it['slide']}"
            if not it.get("product_url") or (CUT_DIR / f"{key}.png").exists() or it.get("image_fetch"):
                continue
            try:
                src = page_image(it["product_url"])
                if not src:
                    raise ValueError("no product image on page")
                r = requests.get(src, headers={"User-Agent": UA, "Referer": it["product_url"]}, timeout=25)
                r.raise_for_status()
                remove_bg(Image.open(io.BytesIO(r.content))).save(CUT_DIR / f"{key}.png", optimize=True)
                print(f"fetched {key}")
            except Exception as e:  # noqa: BLE001 - log and move on
                it["image_fetch"] = f"failed {date.today().isoformat()}: {str(e)[:80]}"
                fails.append(f"{key} {it['name']}: {e}")
    for line in fails:
        print("NO IMAGE", line)
    return fails


def main():
    CUT_DIR.mkdir(parents=True, exist_ok=True)
    INBOX.mkdir(parents=True, exist_ok=True)
    doc = load_fits()
    n = process_inbox(doc)
    if "--no-fetch" not in sys.argv:
        fetch_missing(doc)
    save_fits(doc)
    print(f"inbox processed: {n}")


if __name__ == "__main__":
    main()
