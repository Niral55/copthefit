"""Shared helpers: load/save data, build shop links, captions and the posting queue."""
import json
import re
from pathlib import Path
from urllib.parse import quote_plus, urlparse, urlencode, parse_qsl, urlunparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "fits.json"
CONFIG = ROOT / "config.json"
CUT_DIR = ROOT / "images" / "cut"
PHOTO_DIR = ROOT / "images" / "photos"
INBOX = ROOT / "images" / "inbox"
DIST = ROOT / "dist"

LABELS = ("Exact", "Similar")
ITEM_TYPES = ("watch", "sneakers", "shoes", "clothing", "bag", "jewelry", "accessory")
CATEGORIES = ("Fit", "Kicks", "Wrist")
STATUSES = ("review", "approved", "posted", "rejected")


def load_config():
    return json.loads(CONFIG.read_text())


def load_fits():
    return json.loads(DATA.read_text())


def save_fits(doc):
    DATA.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")


def search_url(cfg, item):
    r = cfg["retailers"].get(item.get("retailer") or "")
    if not r or not item.get("query"):
        return ""
    return r["search"] + quote_plus(item["query"])


def raw_url(cfg, item):
    """Product page if we have one, else a retailer search."""
    return item.get("product_url") or search_url(cfg, item)


def shop_url(cfg, item):
    """Raw URL with affiliate tracking applied (same rules as the site's JS)."""
    u = raw_url(cfg, item)
    if not u:
        return ""
    aff = cfg.get("affiliate", {})
    host = urlparse(u).hostname or ""
    for st in aff.get("stores", []):  # network deep links, e.g. StockX via Impact, Chrono24 via Awin
        d = (st.get("domain") or "").lower().lstrip(".").removeprefix("www.")
        t = st.get("template") or ""
        if d and "{url}" in t and (host == d or host.endswith("." + d)):
            return t.replace("{url}", quote_plus(u))
    if host.endswith("amazon.com"):
        if aff.get("amazon_tag"):
            p = urlparse(u)
            q = dict(parse_qsl(p.query))
            q["tag"] = aff["amazon_tag"]
            u = urlunparse(p._replace(query=urlencode(q)))
        return u
    if host.endswith("ebay.com"):
        if aff.get("ebay_campaign_id"):
            p = urlparse(u)
            q = dict(parse_qsl(p.query))
            q.update(mkcid="1", mkrid="711-53200-19255-0", siteid="0",
                     campid=aff["ebay_campaign_id"], toolid="10001", mkevt="1")
            u = urlunparse(p._replace(query=urlencode(q)))
        return u
    if aff.get("skimlinks_id"):
        return "https://go.skimresources.com/?id=" + quote_plus(aff["skimlinks_id"]) + "&xs=1&url=" + quote_plus(u)
    if aff.get("sovrn_key"):
        return "https://redirect.viglink.com?key=" + quote_plus(aff["sovrn_key"]) + "&u=" + quote_plus(u)
    return u


def retailer_name(cfg, item):
    if item.get("product_url"):
        host = (urlparse(item["product_url"]).hostname or "").replace("www.", "")
        for r in cfg["retailers"].values():
            if (urlparse(r["search"]).hostname or "").replace("www.", "") == host:
                return r["name"]
        return host.split(".")[0].capitalize() if host else ""
    r = cfg["retailers"].get(item.get("retailer") or "")
    return r["name"] if r else ""


def cutout_path(find, item):
    """An item's product cutout. New images are stored per item (item["img"]) so reordering items keeps them."""
    if item.get("img") and (ROOT / item["img"]).exists():
        return ROOT / item["img"]
    p = CUT_DIR / f"{find}-{item['slide']}.png"
    return p if p.exists() else None


def item_key(item):
    import secrets
    if not item.get("id"):
        item["id"] = secrets.token_hex(3)
    return item["id"]


def photo_path(find):
    p = PHOTO_DIR / f"{find}.jpg"
    return p if p.exists() else None


def hashtags(cfg, fit):
    tags = []
    cat_tag = {"Fit": "fitcheck", "Kicks": "sneakers", "Wrist": "watchspotting"}[fit["category"]]
    for t in cfg.get("hashtag_base", []) + [cat_tag] + fit.get("tags", []):
        t = re.sub(r"[^a-z0-9_]", "", t.lower())
        if t and t not in tags:
            tags.append(t)
    return tags[:5]  # Instagram caps hashtags at 5


def caption(cfg, fit):
    kw = (cfg.get("comment_keyword") or "").strip()
    how = f"comment {kw} or tap the link in bio" if kw else "tap the link in bio and search"
    outlet = fit["sources"][0]["label"].split(" — ")[0] if fit.get("sources") else ""
    parts = [
        f"{fit['headline']}\nCop the fit → {how} #{fit['find']}"
        + (" (get it for less there too)" if any(i["label"] == "Similar" for i in fit["items"]) and any(i["label"] == "Exact" for i in fit["items"]) else "")
        + " · affiliate links",
        fit["detail"],
        f"{fit['context']}, {fit['date']}." + (f" Spotted via {outlet}." if outlet else "")
        + (f" Photo: {fit['photo']['credit']}." if (fit.get("photo") or {}).get("credit") and photo_path(fit["find"]) else ""),
        " ".join("#" + t for t in hashtags(cfg, fit)),
    ]
    return "\n\n".join(p for p in parts if p)


def ig_items(fit):
    """Instagram shows the exact pieces only; budget picks live on the site.
    A fit with no exact pieces (brands not reported) shows its picks instead."""
    exact = [it for it in fit["items"] if it["label"] == "Exact"]
    return exact or fit["items"]


def queue(doc):
    """The Instagram queue: live-on-site fits marked ig_queue, in posting order (Post next first, then by Find #).
    The website is not drip-fed; every approved fit is on the site whether or not it's queued here."""
    q = [f for f in doc["fits"] if f["status"] == "approved" and f.get("ig_queue")]
    return sorted(q, key=lambda f: (f.get("priority", 1), int(f["find"])))


def ready_queue(doc, cfg):
    """What the daily job will actually post: the queue, minus fits still waiting on a cover photo."""
    q = queue(doc)
    return [f for f in q if photo_path(f["find"])] if cfg.get("require_photo") else q


def next_find(doc):
    nums = [int(f["find"]) for f in doc["fits"]]
    return f"{(max(nums) if nums else 0) + 1:03d}"


def validate(doc, cfg):
    """Return a list of problems; empty means the data is good to build and post."""
    errs = []
    seen = set()
    for f in doc["fits"]:
        fid = f.get("find", "?")
        if not re.fullmatch(r"\d{3}", fid):
            errs.append(f"{fid}: find must be 3 digits")
        if fid in seen:
            errs.append(f"{fid}: duplicate find")
        seen.add(fid)
        for k in ("celeb", "context", "date", "category", "headline", "detail", "status", "items", "sources"):
            if not f.get(k):
                errs.append(f"{fid}: missing {k}")
        if f.get("category") not in CATEGORIES:
            errs.append(f"{fid}: category must be one of {CATEGORIES}")
        if f.get("status") not in STATUSES:
            errs.append(f"{fid}: status must be one of {STATUSES}")
        if photo_path(fid) and not (f.get("photo") or {}).get("credit"):
            errs.append(f"{fid}: cover photo needs a credit (photo.credit)")
        items = f.get("items", [])
        if not 1 <= len(items) <= 8:
            errs.append(f"{fid}: needs 1-8 items (Instagram allows 10 slides: cover + items + CTA)")
        for n, it in enumerate(items, start=2):
            if it.get("slide") != n:
                errs.append(f"{fid}: item {it.get('name')} should be slide {n}")
            if it.get("type") and it["type"] not in ITEM_TYPES:
                errs.append(f"{fid}-{n}: type must be one of {ITEM_TYPES}")
            if it.get("label") not in LABELS:
                errs.append(f"{fid}-{n}: label must be Exact or Similar")
            if it.get("retailer") and it["retailer"] not in cfg["retailers"]:
                errs.append(f"{fid}-{n}: unknown retailer '{it['retailer']}' (add it to config.json)")
            txt = (it.get("name", "") + " " + it.get("note", "")).lower()
            if re.search(r"\b(dupe|fake|faux|replica)\b", txt):
                errs.append(f"{fid}-{n}: don't use dupe/fake/faux/replica wording")
    return errs
