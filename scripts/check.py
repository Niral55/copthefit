"""Validate data/fits.json and show the posting queue. Exits non-zero if anything is wrong."""
import sys
from datetime import date, timedelta

from common import load_config, load_fits, validate, queue, ready_queue
from dedupe import duplicates


import re

# LEADS.md → Non-negotiables, enforced for new leads ("review")
LUXURY = re.compile(r"\b(louis vuitton|rolex|cartier|audemars|patek|richard mille|tom ford|prada|gucci|dior|chanel|hermès|hermes|"
                    r"saint laurent|balenciaga|bottega|celine|loewe|valentino|hublot|omega|tudor|bvlgari|bulgari|van cleef)\b", re.I)
STOCK = re.compile(r"vecteezy|alamy|shutterstock|dreamstime|cdninstagram|fbcdn|tiktokcdn|pbs\.twimg", re.I)
RESEARCH = re.compile(r"https?://|\bconfirm\b|\bthe article\b|\bsource says\b|\bunverified\b|\bTBD\b|\bcheck (the )?price\b", re.I)


def lead_rules(f):
    e, n = [], f["find"]
    for it in f["items"]:
        if it.get("label") == "Exact" and LUXURY.search(f"{it.get('brand', '')} {it.get('name', '')}"):
            e.append(f"{n}: luxury piece '{it.get('brand')} {it['name']}' (leads must be affordable, LEADS.md rule 1)")
        if not (it.get("image_src") or it.get("img")):
            e.append(f"{n}: item '{it['name']}' has no product image (rule 2)")
    t = (f.get("title") or "").strip()
    if not t or len(t) > 48 or "$" in t:
        e.append(f"{n}: needs a short page title (≤ 40 chars, no prices) (rule 9)")
    if not (f.get("subtitle") or "").strip():
        e.append(f"{n}: needs a page subtitle, e.g. 'Spotted at practice' (rule 9)")
    opts = [o for o in f.get("photo_options") or [] if o.get("image")]
    if not opts and not f.get("photo"):
        e.append(f"{n}: no photos of the person (rule 3)")
    for o in opts:
        if STOCK.search(o["image"]):
            e.append(f"{n}: photo option is a watermarked/expiring link: {o['image'][:60]} (rule 5)")
    return e


def main():
    cfg = load_config()
    doc = load_fits()
    errs = validate(doc, cfg)
    warns = []
    for new, old, why in duplicates(doc):
        errs.append(f"{new['find']}: repeat of #{old['find']} {old['celeb']} · {old['context']} ({why}); remove it")
    for f in doc["fits"]:
        if f["status"] == "review" and not isinstance(f.get("score"), (int, float)):
            errs.append(f"{f['find']}: new leads need a score (see LEADS.md → Score)")
        if f["status"] == "review":
            errs += lead_rules(f)
    for f in doc["fits"]:  # item notes are public on every post
        for it in f["items"]:
            if RESEARCH.search(it.get("note") or ""):
                (errs if f["status"] == "review" else warns).append(f"{f['find']}: item '{it['name']}' note reads like a research note (it's shown on the site); move it to the lead's note")
    for w in warns:
        print("WARNING", w)
    for e in errs:
        print("ERROR", e)
    q = ready_queue(doc, cfg)
    no_photo = len(queue(doc)) - len(q)
    review = [f for f in doc["fits"] if f["status"] == "review"]
    posted = [f for f in doc["fits"] if f["status"] == "posted"]
    print(f"{len(posted)} posted · {len(q)} ready to post · {no_photo} waiting for a cover photo · {len(review)} waiting for review")
    for i, f in enumerate(q[:7]):
        print(f"  {date.today() + timedelta(days=i)}  #{f['find']} {f['celeb']}: {f['headline']}")
    if errs:
        sys.exit(1)


if __name__ == "__main__":
    main()
