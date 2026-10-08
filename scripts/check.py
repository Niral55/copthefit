"""Validate data/fits.json and show the posting queue. Exits non-zero if anything is wrong."""
import sys
from datetime import date, timedelta

from common import load_config, load_fits, validate, queue, ready_queue


def main():
    cfg = load_config()
    doc = load_fits()
    errs = validate(doc, cfg)
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
