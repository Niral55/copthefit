"""Weekly price check (.github/workflows/prices.yml). Reads each item's current price from its store page.

  python scripts/fetch_prices.py fetch prices.json   # visit product pages, write {item key: price}
  python scripts/fetch_prices.py apply prices.json   # write them into data/fits.json (run on the newest main)

Only touches two fields per item: price_auto ("$110") and price_checked (date). A price typed in the admin
("price") always wins on the site. Amazon is skipped on purpose: its rules only allow prices from its own API.
Most stores publish the price for Google Shopping (JSON-LD "offers" or product:price meta tags); that's what's read.
"""
import json
import re
import sys
import time
from datetime import date
from urllib.parse import urlparse

import requests

from common import ROOT, load_fits, save_fits

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en-US,en;q=0.9"}
SKIP = re.compile(r"(^|\.)(amazon\.[a-z.]+|amzn\.to|a\.co)$", re.I)
SYMBOL = {"USD": "$", "GBP": "£", "EUR": "€", "CAD": "CA$", "AUD": "A$", "JPY": "¥"}


def key(fit, it):
    return f"{fit['find']}|{it.get('product_url')}"


def money(amount, cur):
    try:
        v = float(str(amount).replace(",", ""))
    except ValueError:
        return ""
    if v <= 0:
        return ""
    s = f"{v:,.0f}" if v == int(v) else f"{v:,.2f}"
    return f"{SYMBOL.get((cur or 'USD').upper(), (cur or '') + ' ')}{s}"


def offers_price(node):
    """Find (price, currency) in a JSON-LD blob (Product → offers, possibly nested / lists / @graph)."""
    if isinstance(node, list):
        for n in node:
            r = offers_price(n)
            if r:
                return r
        return None
    if not isinstance(node, dict):
        return None
    for k in ("price", "lowPrice"):
        if k in node and node[k] not in (None, ""):
            return node[k], node.get("priceCurrency") or (node.get("priceSpecification") or {}).get("priceCurrency")
    for k in ("offers", "@graph", "priceSpecification", "mainEntity", "hasVariant"):
        if k in node:
            r = offers_price(node[k])
            if r:
                return r
    return None


def read_price(html):
    for blob in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(blob.strip())
        except ValueError:
            continue
        if "Product" in json.dumps(data)[:20000]:
            r = offers_price(data)
            if r:
                return money(*r)
    m = re.search(r'<meta[^>]+(?:property|name)="(?:product:price:amount|og:price:amount)"[^>]+content="([\d.,]+)"', html, re.I)
    if m:
        c = re.search(r'<meta[^>]+(?:property|name)="(?:product:price:currency|og:price:currency)"[^>]+content="([A-Z]{3})"', html, re.I)
        return money(m.group(1), c.group(1) if c else "USD")
    m = re.search(r'itemprop="price"[^>]+content="([\d.,]+)"', html, re.I)
    return money(m.group(1), "USD") if m else ""


def fetch(out):
    doc, res = load_fits(), {}
    for fit in doc["fits"]:
        if fit["status"] not in ("approved", "posted", "review"):
            continue
        for it in fit["items"]:
            url = it.get("product_url") or ""
            host = urlparse(url).netloc.lower().removeprefix("www.")
            if not url or SKIP.search(host):
                continue
            try:
                r = requests.get(url, headers=UA, timeout=25)
                p = read_price(r.text) if r.status_code == 200 else ""
            except requests.RequestException:
                p = ""
            res[key(fit, it)] = p
            print(f"#{fit['find']} {host}: {p or '-'}")
            time.sleep(1)
    json.dump(res, open(out, "w"), indent=1)
    found = sum(1 for v in res.values() if v)
    print(f"{found} of {len(res)} prices found")
    res["__summary__"] = f"{found} of {len(res)} store links had a readable price"


def apply(src):
    res, doc, today = json.load(open(src)), load_fits(), date.today().isoformat()
    st_path = ROOT / "data" / "status.json"  # so the admin (and Claude) can see how the last check went
    try:
        st = json.loads(st_path.read_text())
    except (OSError, ValueError):
        st = {}
    st["prices"] = {"last_run": today, "message": res.pop("__summary__", "")}
    st_path.write_text(json.dumps(st, indent=1) + "\n")
    for fit in doc["fits"]:
        for it in fit["items"]:
            k = key(fit, it)
            if k not in res:
                continue
            if res[k]:
                it["price_auto"], it["price_checked"] = res[k], today
            else:  # couldn't read it this week: drop the old one rather than show a stale price
                it.pop("price_auto", None)
                it.pop("price_checked", None)
    save_fits(doc)


if __name__ == "__main__":
    {"fetch": fetch, "apply": apply}[sys.argv[1]](sys.argv[2])
