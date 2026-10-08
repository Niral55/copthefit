"""Validate data/fits.json and show the posting queue. Exits non-zero if anything is wrong."""
import sys
from datetime import date, timedelta

from common import load_config, load_fits, validate, queue


def main():
    cfg = load_config()
    doc = load_fits()
    errs = validate(doc, cfg)
    for e in errs:
        print("ERROR", e)
    q = queue(doc)
    review = [f for f in doc["fits"] if f["status"] == "review"]
    posted = [f for f in doc["fits"] if f["status"] == "posted"]
    print(f"{len(posted)} posted · {len(q)} in queue · {len(review)} waiting for review")
    for i, f in enumerate(q[:7]):
        print(f"  {date.today() + timedelta(days=i)}  #{f['find']} {f['celeb']}: {f['headline']}")
    if errs:
        sys.exit(1)


if __name__ == "__main__":
    main()
