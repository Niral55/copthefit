"""Build the public site into dist/: index.html, fits.json, fonts, product images.

Shows every approved or posted fit (all links live, whether or not Instagram has posted it yet).
"""
import json
import shutil
import sys

from common import ROOT, DIST, CUT_DIR, load_config, load_fits, raw_url, retailer_name, cutout_path, photo_path, validate


def main():
    cfg = load_config()
    doc = load_fits()
    errs = validate(doc, cfg)
    if errs:
        print("\n".join(errs))
        sys.exit("Fix data/fits.json before building.")

    DIST.mkdir(exist_ok=True)
    (DIST / "fonts").mkdir(exist_ok=True)
    for f in (ROOT / "assets" / "fonts").glob("*.woff2"):
        shutil.copy(f, DIST / "fonts" / f.name)
    (DIST / "img").mkdir(exist_ok=True)

    public = []
    for fit in sorted(doc["fits"], key=lambda f: int(f["find"])):
        if fit["status"] not in ("approved", "posted"):
            continue
        items = []
        for it in fit["items"]:
            cut = cutout_path(fit["find"], it["slide"])
            if cut:
                shutil.copy(cut, DIST / "img" / cut.name)
            items.append(dict(
                slide=it["slide"], label=it["label"], brand=it.get("brand", ""), name=it["name"],
                retailer_name=retailer_name(cfg, it), url=raw_url(cfg, it), note=it.get("note", ""),
                image=f"img/{cut.name}" if cut else ""))
        first = next((i["image"] for i in items if i["image"] and i["label"] == "Exact"), "") or \
            next((i["image"] for i in items if i["image"]), "")
        cover, credit = "", ""
        ph = photo_path(fit["find"])
        mode = cfg.get("site_photos", "free")  # "free" = only public-domain/CC photos, "all", or "none"
        meta = fit.get("photo") or {}
        if ph and (mode == "all" or (mode == "free" and meta.get("license"))):
            shutil.copy(ph, DIST / "img" / f"photo-{fit['find']}.jpg")
            cover, credit = f"img/photo-{fit['find']}.jpg", meta.get("credit", "")
        public.append(dict(cover=cover, cover_credit=credit,
            find=fit["find"], celeb=fit["celeb"], context=fit["context"], date=fit["date"],
            category=fit["category"], timing=fit.get("timing", ""), headline=fit["headline"],
            detail=fit["detail"], sources=fit["sources"], note=fit.get("note", ""),
            image=first, ig=fit.get("ig_permalink") or "", items=items))

    aff = cfg.get("affiliate", {})
    js_cfg = dict(amazonTag=aff.get("amazon_tag", ""), ebayCampaignId=aff.get("ebay_campaign_id", ""),
                  skimlinksId=aff.get("skimlinks_id", ""), sovrnKey=aff.get("sovrn_key", ""), overrides={})
    dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = (ROOT / "templates" / "site.html").read_text()
    html = html.replace("/*__DATA__*/[]", dump(public), 1)
    i = html.index("/*__CONFIG__*/")
    j = html.index("};", i) + 1
    html = html[:i] + dump(js_cfg) + html[j:]
    (DIST / "index.html").write_text("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
                                     "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
                                     + html.replace("<div class=\"wrap\">", "</head>\n<body>\n<div class=\"wrap\">", 1)
                                     + "\n</body>\n</html>\n")
    (DIST / "fits.json").write_text(dump(public))
    (DIST / ".nojekyll").write_text("")
    if cfg.get("custom_domain"):
        (DIST / "CNAME").write_text(cfg["custom_domain"].strip() + "\n")
    print(f"site: {len(public)} fits, {sum(len(f['items']) for f in public)} items")


if __name__ == "__main__":
    main()
