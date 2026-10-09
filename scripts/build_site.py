"""Build the public site into dist/: index.html, fits.json, fonts, product images.

Shows every approved or posted fit (all links live, whether or not Instagram has posted it yet).
"""
import html as H
import json
import re
import shutil
import sys
import unicodedata

from common import ROOT, DIST, CUT_DIR, load_config, load_fits, raw_url, shop_url, retailer_name, cutout_path, photo_path, validate

e = lambda t: H.escape(str(t or ""), quote=True)


def slugify(t):
    t = unicodedata.normalize("NFKD", t.replace("$", "s").replace("&", " and ")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def clip(t, n):
    t = " ".join(str(t).split())
    return t if len(t) <= n else t[:n - 1].rsplit(" ", 1)[0].rstrip(",;:-") + "…"


NOUN = {"Fit": "outfit", "Kicks": "sneakers", "Wrist": "watch"}


def fit_title(f):
    """Search-style title: who + where + the named pieces, ~60 chars."""
    brands = []
    for it in f["items"]:
        b = it["brand"] if it["label"] == "Exact" else ""
        if b and b not in brands:
            brands.append(b)
    ctx = re.sub(r"\s*[,(].*$", "", re.sub(r"\s*,?\s*(19|20)\d\d$", "", f["context"]))
    base = f"{f['celeb']}'s {ctx} {NOUN.get(f['category'], 'outfit')}"
    if brands:
        full = f"{base}: {', '.join(brands[:3])}"
        if len(full) <= 70:
            base = full
    return base


def fit_desc(f):
    exact = [it for it in f["items"] if it["label"] == "Exact"]
    tail = " Shop the exact pieces and cheaper alternatives." if exact else " Shop similar pieces."
    return clip(f["detail"], 158 - len(tail)) + tail


def head(cfg, title, desc, url, image, kind="website", ld=None):
    site = cfg["site_url"].rstrip("/")
    tags = [f"<title>{e(title)}</title>",
            '<link rel="icon" href="favicon.svg" type="image/svg+xml">',
            '<link rel="icon" href="favicon-32.png" sizes="32x32" type="image/png">',
            '<link rel="apple-touch-icon" href="apple-touch-icon.png">',
            f'<meta name="description" content="{e(desc)}">',
            f'<link rel="canonical" href="{e(url)}">',
            f'<meta property="og:site_name" content="Cop the Fit">',
            f'<meta property="og:type" content="{kind}">',
            f'<meta property="og:title" content="{e(title)}">',
            f'<meta property="og:description" content="{e(desc)}">',
            f'<meta property="og:url" content="{e(url)}">',
            f'<meta name="twitter:card" content="{"summary_large_image" if image else "summary"}">',
            f'<meta name="robots" content="index,follow,max-image-preview:large">']
    if image:
        tags += [f'<meta property="og:image" content="{e(site + "/" + image)}">',
                 f'<meta name="twitter:image" content="{e(site + "/" + image)}">']
    for block in ld or []:
        tags.append('<script type="application/ld+json">' + json.dumps(block, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    return "\n".join(tags)


def ssr_fit(cfg, f, raw, prev, nxt):
    """Static version of the fit page (same markup the JS renders), so search engines see it without JS."""
    def row(pub, it):
        url = shop_url(cfg, it)
        act = (f'<a class="shop" href="{e(url)}" target="_blank" rel="sponsored nofollow noopener">Shop on {e(pub["retailer_name"] or "retailer")} ↗</a>'
               if url else '<span class="nosale">Not for sale</span>')
        img = (f'<img class="thumb" src="{e(pub["image"])}" alt="{e((pub["brand"] + " " + pub["name"]).strip())}" loading="lazy">'
               if pub["image"] else '<span class="thumb ph">Image coming</span>')
        return (f'<li class="item has-img">{img}<div style="min-width:0">'
                + (f'<div class="brand">{e(pub["brand"])}</div>' if pub["brand"] else "")
                + f'<div class="name">{e(pub["name"])}</div>'
                + (f'<div class="note">{e(pub["note"])}</div>' if pub["note"] else "")
                + f'</div><div class="act">{act}</div></li>')
    pairs = list(zip(f["items"], raw["items"]))
    exact = [p for p in pairs if p[0]["label"] == "Exact"]
    cheap = [p for p in pairs if p[0]["label"] != "Exact"]
    out = ['<a class="back" href="./">← All finds</a><article class="fit"><aside class="bigtag"><div class="hole" aria-hidden="true"></div>',
           '<figure class="look"><div class="frame">'
           + (f'<img src="{e(f["cover"])}" alt="{e(f["celeb"])} at {e(f["context"])}">' if f["cover"] else '<div class="ph">Photo of the look coming</div>')
           + "</div>" + (f'<figcaption>Photo: {e(f["cover_credit"])}</figcaption>' if f["cover_credit"] else "") + "</figure>",
           f'<div><div class="label">Find</div><div class="bignum">#{f["find"]}</div></div>',
           f'<dl><dt>Who</dt><dd>{e(f["celeb"])}</dd><dt>Where</dt><dd>{e(f["context"])}</dd><dt>When</dt><dd>{e(f["date"])}</dd>'
           f'<dt>Items</dt><dd>{len(exact)} exact · {len(cheap)} similar</dd></dl></aside>',
           f'<div style="min-width:0"><p class="celeb">What {e(f["celeb"])} wore · {e(f["context"])}</p><h1>{e(f["headline"])}</h1><p class="detail">{e(f["detail"])}</p>']
    if exact:
        out.append('<h2 class="sect">The exact fit</h2><ol class="items">' + "".join(row(a, b) for a, b in exact) + "</ol>")
    if cheap:
        sub = "Similar pieces at a lower price. Not the exact items worn." if exact else "The brands weren't reported, so these are similar picks."
        out.append(f'<h2 class="sect">{"Get it for less" if exact else "Get the look"}</h2><p class="sect-sub">{sub}</p><ol class="items cheap">'
                   + "".join(row(a, b) for a, b in cheap) + "</ol>")
    out.append('<div class="sources"><h2>Spotted via</h2><ul>'
               + "".join(f'<li><a href="{e(x["url"])}" target="_blank" rel="noopener">{e(x["label"])}</a></li>' for x in f["sources"]) + "</ul></div>")
    out.append('<nav class="pager">'
               + (f'<a href="f/{prev["slug"]}/">← #{prev["find"]} {e(prev["celeb"])}</a>' if prev else "<span></span>")
               + (f'<a href="f/{nxt["slug"]}/">#{nxt["find"]} {e(nxt["celeb"])} →</a>' if nxt else "<span></span>")
               + "</nav></div></article>")
    return "".join(out)


def ssr_home(public):
    cards = []
    for f in sorted(public, key=lambda x: -int(x["find"])):
        pic = (f'<span class="pic photo"><img src="{e(f["cover"])}" alt="{e(f["celeb"])} at {e(f["context"])}" loading="lazy"></span>' if f["cover"]
               else f'<span class="pic"><img src="{e(f["image"])}" alt="" loading="lazy"></span>' if f["image"]
               else '<span class="pic"><span class="ph">Photo coming</span></span>')
        cards.append(f'<a class="tagcard" href="f/{f["slug"]}/">{pic}<span class="num">FIND #{f["find"]}</span><span class="who">{e(f["celeb"])}</span>'
                     f'<span class="hl">{e(f["headline"])}</span><span class="meta"><span>{e(f["category"])}</span><span>{len(f["items"])} items</span><span>{e(f["date"])}</span></span></a>')
    return f'<p class="count">{len(public)} finds · newest first</p><div class="grid">' + "".join(cards) + "</div>"


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
            cut = cutout_path(fit["find"], it)
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
        public.append(dict(cover=cover, cover_credit=credit, slug=f"{fit['find']}-{slugify(fit['celeb'])}-{slugify(re.sub(r'[,(].*$', '', fit['context']))}"[:72].strip("-") + "-" + NOUN.get(fit["category"], "outfit"),
            find=fit["find"], celeb=fit["celeb"], context=fit["context"], date=fit["date"],
            category=fit["category"], timing=fit.get("timing", ""), headline=fit["headline"],
            detail=fit["detail"], sources=fit["sources"], note=fit.get("note", ""),
            image=first, ig=fit.get("ig_permalink") or "", items=items))

    aff = cfg.get("affiliate", {})
    js_cfg = dict(amazonTag=aff.get("amazon_tag", ""), ebayCampaignId=aff.get("ebay_campaign_id", ""),
                  skimlinksId=aff.get("skimlinks_id", ""), sovrnKey=aff.get("sovrn_key", ""), overrides={})
    dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    tpl = (ROOT / "templates" / "site.html").read_text()
    i = tpl.index("/*__CONFIG__*/")
    j = tpl.index("};", i) + 1
    tpl = tpl[:i] + dump(js_cfg) + tpl[j:]
    tpl = tpl.replace("/*__DATA__*/[]", dump(public), 1)
    site = cfg["site_url"].rstrip("/")

    def page(path, head_html, ssr, find="", base=""):
        body = tpl.replace("<!--__HEAD__-->", (f'<base href="{base}">\n' if base else "") + head_html, 1)
        body = body.replace("<!--__SSR__-->", ssr, 1).replace('/*__PAGE__*/""', json.dumps(find), 1)
        out = DIST / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
                       "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
                       + body.replace("<div class=\"wrap\">", "</head>\n<body>\n<div class=\"wrap\">", 1) + "\n</body>\n</html>\n")

    home_title = "Cop the Fit: Celebrity Outfits Identified, Shop the Look"
    home_desc = clip("Every celebrity fit, identified: athletes, musicians and actors. See exactly what they wore and shop the pieces, or get the look for less.", 158)
    home_img = next((f["cover"] or f["image"] for f in sorted(public, key=lambda x: -int(x["find"])) if f["cover"] or f["image"]), "")
    home_ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": "Cop the Fit", "url": site + "/"},
               {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
                   {"@type": "ListItem", "position": n + 1, "url": f"{site}/f/{f['slug']}/", "name": fit_title(f)}
                   for n, f in enumerate(sorted(public, key=lambda x: -int(x["find"])))]}]
    page("index.html", head(cfg, home_title, home_desc, site + "/", home_img, ld=home_ld), ssr_home(public))
    page("404.html", head(cfg, "Not found · Cop the Fit", home_desc, site + "/", home_img) + '\n<meta name="robots" content="noindex">', ssr_home(public), base=site + "/")

    raw_by = {f["find"]: f for f in doc["fits"]}
    urls = [(site + "/", max([f.get("updated", f.get("added", "")) for f in doc["fits"]] or [""])[:10])]
    for n, f in enumerate(public):
        raw = raw_by[f["find"]]
        url = f"{site}/f/{f['slug']}/"
        title = fit_title(f)
        img = f["cover"] or f["image"]
        ld = [{"@context": "https://schema.org", "@type": "Article", "headline": clip(f["headline"], 110), "description": fit_desc(f),
               "datePublished": raw.get("posted_at") or raw.get("added"), "dateModified": (raw.get("updated") or raw.get("added") or "")[:10] or None,
               "author": {"@type": "Organization", "name": "Cop the Fit", "url": site + "/"},
               "publisher": {"@type": "Organization", "name": "Cop the Fit"}, "mainEntityOfPage": url,
               "about": {"@type": "Person", "name": f["celeb"]}, **({"image": [site + "/" + img]} if img else {}),
               "mentions": [{"@type": "Product", "name": it["name"], **({"brand": {"@type": "Brand", "name": it["brand"]}} if it["brand"] else {})}
                            for it in f["items"] if it["label"] == "Exact"]},
              {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                  {"@type": "ListItem", "position": 1, "name": "Cop the Fit", "item": site + "/"},
                  {"@type": "ListItem", "position": 2, "name": f"#{f['find']} {f['celeb']}", "item": url}]}]
        ld[0] = {k: v for k, v in ld[0].items() if v}
        page(f"f/{f['slug']}/index.html", head(cfg, f"{title} | Cop the Fit", fit_desc(f), url, img, kind="article", ld=ld),
             ssr_fit(cfg, f, raw, public[n - 1] if n else None, public[n + 1] if n + 1 < len(public) else None),
             find=f["find"], base="../../")
        urls.append((url, (raw.get("updated") or raw.get("added") or "")[:10]))

    (DIST / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{e(u)}</loc>" + (f"<lastmod>{d}</lastmod>" if d else "") + "</url>\n" for u, d in urls) + "</urlset>\n")
    # robots.txt only counts at the domain root, so it takes effect once a custom domain is set.
    (DIST / "robots.txt").write_text(f"User-agent: *\nDisallow: /admin.html\n\nSitemap: {site}/sitemap.xml\n")
    (DIST / "fits.json").write_text(dump(public))
    shutil.copy(ROOT / "templates" / "admin.html", DIST / "admin.html")
    for icon in ("favicon.svg", "favicon-32.png", "apple-touch-icon.png"):
        shutil.copy(ROOT / "assets" / icon, DIST / icon)
    shutil.copy(ROOT / "assets" / "favicon-32.png", DIST / "favicon.ico")  # browsers that ask for /favicon.ico
    (DIST / ".nojekyll").write_text("")
    if cfg.get("custom_domain"):
        (DIST / "CNAME").write_text(cfg["custom_domain"].strip() + "\n")
    print(f"site: {len(public)} fits, {sum(len(f['items']) for f in public)} items")


if __name__ == "__main__":
    main()
