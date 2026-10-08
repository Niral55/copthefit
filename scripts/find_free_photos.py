"""Find free-to-use photos of each look on Wikimedia Commons (public domain, CC0, CC BY, CC BY-SA).

For every approved or review fit without a cover photo:
- searches Commons for the celebrity around the event date
- keeps only licenses that allow commercial use with credit
- same-day match (±1 day) -> downloads it as the cover photo with the credit filled in
- same-month matches -> saved as `photo_candidates` for you to check in the extension

Run by the build workflow (it has open internet). Usage: python scripts/find_free_photos.py
"""
import re
from datetime import date, datetime, timedelta
from io import BytesIO

import requests
from PIL import Image

from common import PHOTO_DIR, load_fits, save_fits, photo_path

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "CopTheFit/1.0 (https://github.com/; photo credit bot)"}
OK_LICENSES = re.compile(r"^(public domain|pd|cc0|cc[- ]by(-sa)?([- ]\d\.\d)?( [a-z]{2,})?)", re.I)
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def event_date(text):
    """'Aug 31, 2026' -> (date, 'day'); 'Sept 2026' -> (date, 'month'); '2026' -> (None, None)."""
    m = re.match(r"([A-Za-z]{3,})\.?\s+(\d{1,2}),\s*(\d{4})", text or "")
    if m and m.group(1)[:3].lower() in MONTHS:
        return date(int(m.group(3)), MONTHS[m.group(1)[:3].lower()], int(m.group(2))), "day"
    m = re.match(r"(?:Late |Early |Mid )?([A-Za-z]{3,})\.?\s+(\d{4})", text or "")
    if m and m.group(1)[:3].lower() in MONTHS:
        return date(int(m.group(2)), MONTHS[m.group(1)[:3].lower()], 1), "month"
    return None, None


def strip_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


def photo_date(meta):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", meta.get("DateTimeOriginal", {}).get("value", ""))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def search(celeb, year):
    params = {
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 40,
        "gsrsearch": f'filetype:bitmap "{celeb}" {year}', "prop": "imageinfo",
        "iiprop": "url|extmetadata|size", "iiurlwidth": 1600,
    }
    r = requests.get(API, params=params, headers=UA, timeout=30)
    r.raise_for_status()
    return list((r.json().get("query") or {}).get("pages", {}).values())


def candidates(fit):
    when, precision = event_date(fit["date"])
    if not when:
        return []
    out = []
    last = fit["celeb"].split()[-1].lower()
    for page in search(fit["celeb"], when.year):
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        lic = strip_html(meta.get("LicenseShortName", {}).get("value", ""))
        if not OK_LICENSES.match(lic) or "nc" in lic.lower() or "nd" in lic.lower().split("-"):
            continue
        if last not in page.get("title", "").lower() + strip_html(meta.get("ImageDescription", {}).get("value", "")).lower():
            continue
        if info.get("height", 0) < 800:
            continue
        taken = photo_date(meta)
        if not taken:
            continue
        if precision == "day" and abs((taken - when).days) <= 1:
            match = "day"
        elif taken.year == when.year and taken.month == when.month:
            match = "month"
        else:
            continue
        out.append({
            "match": match, "taken": taken.isoformat(), "license": lic,
            "author": strip_html(meta.get("Artist", {}).get("value", ""))[:80] or "Unknown",
            "page": info.get("descriptionurl", ""), "image": info.get("thumburl") or info.get("url", ""),
        })
    out.sort(key=lambda c: (c["match"] != "day", c["taken"]))
    return out[:5]


def main():
    doc = load_fits()
    adopted = listed = 0
    for fit in doc["fits"]:
        if fit["status"] not in ("approved", "review") or photo_path(fit["find"]) or fit.get("photo_search"):
            continue
        try:
            cands = candidates(fit)
        except Exception as e:  # noqa: BLE001
            print(f"#{fit['find']}: search failed ({e})")
            continue
        fit["photo_search"] = date.today().isoformat()  # search each fit once; delete this field to retry
        best = next((c for c in cands if c["match"] == "day"), None)
        if best:
            img = Image.open(BytesIO(requests.get(best["image"], headers=UA, timeout=60).content)).convert("RGB")
            img.thumbnail((1600, 1600))
            PHOTO_DIR.mkdir(parents=True, exist_ok=True)
            img.save(PHOTO_DIR / f"{fit['find']}.jpg", quality=88, optimize=True)
            fit["photo"] = {"credit": f"{best['author']} / {best['license']} via Wikimedia Commons",
                            "source_url": best["page"], "license": best["license"]}
            adopted += 1
            print(f"#{fit['find']} {fit['celeb']}: free photo from {best['taken']} ({best['license']})")
        elif cands:
            fit["photo_candidates"] = cands
            listed += 1
            print(f"#{fit['find']} {fit['celeb']}: {len(cands)} same-month free photos to check")
    save_fits(doc)
    print(f"free photos: {adopted} added as covers, {listed} fits with candidates to check")


if __name__ == "__main__":
    main()
