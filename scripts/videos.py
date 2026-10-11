"""Write VIDEOS.md: which Find #s go in which video (from data/videos.json + data/fits.json).

  python scripts/videos.py        # regenerate VIDEOS.md
Each listing's "video" field says which video it belongs to; data/videos.json holds the order and titles.
"""
import json
import os

from common import ROOT, load_fits

PHOTO = ROOT / "images" / "photos"


def main():
    vids = json.loads((ROOT / "data" / "videos.json").read_text())
    by = {f["find"]: f for f in load_fits()["fits"]}

    def row(x):
        f = by.get(x)
        if not f:
            return f"| #{x} | (missing) | | | | |"
        ex = [i for i in f["items"] if i["label"] == "Exact"] or f["items"][:1]
        it = ex[0] if ex else {}
        price = it.get("price") or it.get("price_auto") or ""
        status = {"approved": "live", "posted": "live", "review": "lead", "rejected": "rejected"}.get(f["status"], f["status"])
        cover = "yes" if (PHOTO / f"{x}.jpg").exists() else "**no**"
        item = f"{it.get('brand', '')} {it.get('name', '')}".strip()
        return f"| #{x} | {f['celeb']} | {item[:60]} | {price} | {status} | {cover} |"

    head = "| Find # | Who | Item | Price | Status | Cover |\n|---|---|---|---|---|---|"
    out = ["# Video plan", "", "Generated from `data/videos.json` (`python scripts/videos.py`). Find #s in each video are consecutive.", ""]
    for n, v in enumerate(vids["videos"], start=1):
        ok = len(v["finds"]) >= 5
        out += [f"## {n}. {v['title']}", "", f"Format: {v['format']} · {len(v['finds'])} listing{'s' if len(v['finds']) != 1 else ''}"
                + ("" if ok else f" (needs {5 - len(v['finds'])} more for a 5-celeb video)"), "", head]
        out += [row(x) for x in v["finds"]] + [""]
    out += ["## No video yet (candidates to delist)", "", head] + [row(x) for x in vids.get("no_video", [])] + [""]
    (ROOT / "VIDEOS.md").write_text("\n".join(out))
    print("wrote VIDEOS.md")


if __name__ == "__main__":
    main()
