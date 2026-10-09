"""Clean up products saved with the Chrome extension ("Save product to Cop the Fit").

For every product in data/products.json that hasn't been enriched yet:
- with ANTHROPIC_API_KEY set (a GitHub repo secret): Claude writes a short clean name, fills the brand,
  sorts it into a category and suggests which post it belongs to (and Exact vs Similar);
- without a key: a simple rule-based cleanup of the store title, so the product is still usable.

Runs from .github/workflows/enrich.yml whenever products.json changes.
"""
import json
import os
import re
import sys

import requests

from common import ROOT, load_fits
from item_types import guess_type

PRODUCTS = ROOT / "data" / "products.json"
MODEL = os.environ.get("ENRICH_MODEL", "claude-haiku-5-5")


def load():
    return json.loads(PRODUCTS.read_text()) if PRODUCTS.exists() else {"products": []}


def basic_clean(p):
    """No-AI fallback: drop the brand prefix and keyword-stuffed tail from store titles."""
    t = re.sub(r"\s+", " ", p.get("title_raw") or p.get("name") or "").strip()
    brand = (p.get("brand") or "").strip()
    if brand and t.lower().startswith(brand.lower()):
        t = t[len(brand):].lstrip(" -–:|,")
    t = re.split(r"\s[|–-]\s|, (?=[A-Z0-9])|\(|\[", t)[0].strip()
    if len(t) > 60:
        t = t[:60].rsplit(" ", 1)[0]
    return t or p.get("title_raw", "")[:60]


def recent_posts(n=60):
    fits = [f for f in load_fits()["fits"] if f["status"] in ("approved", "posted", "review")]
    fits.sort(key=lambda f: -int(f["find"]))
    return [{"find": f["find"], "celeb": f["celeb"], "context": f["context"],
             "items": [f"{i['label']}: {i.get('brand', '')} {i['name']}".strip() for i in f["items"]]} for f in fits[:n]]


def ai_enrich(p, posts, key):
    prompt = f"""You tidy up product listings for a men's celebrity-outfit site. Each post shows what a celebrity wore
("Exact" pieces) plus cheaper look-alikes ("Similar").

Product saved from a store page:
- store: {p.get('store')}
- page title: {p.get('title_raw')}
- brand on page: {p.get('brand') or 'unknown'}
- price: {p.get('price') or 'unknown'} {p.get('currency') or ''}
- url: {p.get('url')}

Recent posts (Find #, who, where, items):
{json.dumps(posts, ensure_ascii=False)}

Reply with only a JSON object:
{{"brand": "brand name, properly capitalised, or empty if unbranded/generic",
  "name": "short clean product name WITHOUT the brand, max 45 characters, the way a style editor would write it (e.g. 'Speedmaster Moonwatch', 'Automatic tonneau watch, brown leather'); no SEO keywords",
  "category": "watch | sneakers | shoes | clothing | accessory | jewelry | bag",
  "suggested_find": "the Find # of the post this product most likely belongs to, or null if none fits",
  "label": "Exact if it is the very item named in that post, otherwise Similar",
  "reason": "one short sentence on why that post (or why none)"}}"""
    r = requests.post("https://api.anthropic.com/v1/messages", timeout=60, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": MODEL, "max_tokens": 400, "messages": [{"role": "user", "content": prompt}]})
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json().get("content", []))
    m = re.search(r"\{.*\}", text, re.S)
    out = json.loads(m.group(0)) if m else {}
    finds = {x["find"] for x in posts}
    sf = (str(out.get("suggested_find") or "").strip().lstrip("#") or None)
    return {"brand": (out.get("brand") or "").strip()[:40], "name": (out.get("name") or "").strip()[:60],
            "category": out.get("category") or "", "suggested_find": sf.zfill(3) if sf and sf.zfill(3) in finds else None,
            "label": "Exact" if out.get("label") == "Exact" else "Similar", "reason": (out.get("reason") or "")[:160]}


def main():
    doc = load()
    todo = [p for p in doc["products"] if not p.get("enriched")]
    if not todo:
        print("nothing to enrich")
        return
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    posts = recent_posts() if key else []
    for p in todo:
        p.setdefault("brand", "")
        try:
            if key:
                ai = ai_enrich(p, posts, key)
                p.update({k: v for k, v in ai.items() if v not in ("", None) or k == "suggested_find"})
                p["name"] = p.get("name") or basic_clean(p)
                p["enriched"] = "ai"
            else:
                p["name"] = p.get("name") or basic_clean(p)
                p["enriched"] = "basic"
            if p.get("category") not in ("watch", "sneakers", "shoes", "clothing", "bag", "jewelry", "accessory"):
                p["category"] = guess_type(p.get("title_raw", ""), p.get("brand", ""))
            print(f"{p['id']}: {p.get('brand')} | {p['name']} -> {p.get('suggested_find')}")
        except Exception as e:  # noqa: BLE001 - keep the product, try the basic cleanup
            print(f"{p['id']}: AI failed ({e}); using basic cleanup", file=sys.stderr)
            p["name"] = p.get("name") or basic_clean(p)
            p["enriched"] = "basic"
    if not key:
        print("No ANTHROPIC_API_KEY secret: used basic cleanup. Add the secret to get AI names and post suggestions.")
    PRODUCTS.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
