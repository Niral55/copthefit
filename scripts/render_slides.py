"""Render each fit's carousel to 1080x1350 JPEGs: dist/slides/<find>/01.jpg ... plus caption.txt.

Usage: python scripts/render_slides.py            # every fit waiting to post (approved + review)
       python scripts/render_slides.py 003 014    # just these Find #s
"""
import json
import sys
from playwright.sync_api import sync_playwright

from common import ROOT, DIST, load_config, load_fits, caption, retailer_name, raw_url, cutout_path

TEMPLATE = (ROOT / "templates" / "slide.html").as_uri()


def slides_for(cfg, fit):
    items = fit["items"]
    total = len(items) + 2
    first_img = next((cutout_path(fit["find"], it["slide"]) for it in items
                      if it["label"] == "Exact" and cutout_path(fit["find"], it["slide"])), None)
    outlet = fit["sources"][0]["label"].split(" — ")[0] if fit.get("sources") else ""
    out = [dict(type="cover", find=fit["find"], headline=fit["headline"], context=fit["context"],
                date=fit["date"], outlet=outlet, image=first_img.as_uri() if first_img else "",
                items=[dict(label=i["label"], brand=i.get("brand", ""), name=i["name"]) for i in items])]
    for it in items:
        img = cutout_path(fit["find"], it["slide"])
        out.append(dict(type="item", find=fit["find"], idx=it["slide"], total=total,
                        image=img.as_uri() if img else "",
                        item=dict(label=it["label"], brand=it.get("brand", ""), name=it["name"],
                                  retailer=retailer_name(cfg, it), custom=not raw_url(cfg, it))))
    out.append(dict(type="cta", find=fit["find"], total=total,
                    handle=cfg.get("instagram_handle", ""), keyword=cfg.get("comment_keyword", "")))
    return out


def main(only):
    cfg = load_config()
    doc = load_fits()
    fits = [f for f in doc["fits"] if (f["find"] in only) or (not only and f["status"] in ("approved", "review"))]
    problems = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350})
        page.goto(TEMPLATE)
        for fit in fits:
            folder = DIST / "slides" / fit["find"]
            folder.mkdir(parents=True, exist_ok=True)
            for old in folder.glob("*.jpg"):
                old.unlink()
            for n, s in enumerate(slides_for(cfg, fit), start=1):
                ok = page.evaluate("d => window.render(d)", s)
                if not ok:
                    problems.append(f"{fit['find']} slide {n} overflows")
                page.locator("#slide").screenshot(path=str(folder / f"{n:02d}.jpg"), type="jpeg", quality=90)
            (folder / "caption.txt").write_text(caption(cfg, fit))
        browser.close()
    print(f"rendered {len(fits)} carousels")
    for pr in problems:
        print("WARN", pr)


if __name__ == "__main__":
    main(set(sys.argv[1:]))
