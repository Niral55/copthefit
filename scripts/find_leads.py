"""Find new leads with Claude (Anthropic API + web search). Run by the "Find leads" button in the admin page
(.github/workflows/leads.yml), never on a schedule.

Claude reads LEADS.md (the rules), data/events.json (what just happened), the list of fits already on file
and the current category mix, searches the web, and returns leads as JSON. This script then:
  - drops anything that repeats a fit on file (dedupe.py, any status) or another new lead,
  - drops leads that fail the data checks (validate),
  - numbers them, saves them as "review" leads, and leaves a note in data/status.json for the admin page.

Env: ANTHROPIC_API_KEY (repo secret), COUNT ("" = let the calendar decide), FOCUS (optional, e.g. "NBA tunnel fits"),
     LEADS_MODEL (default claude-sonnet-5-5).
"""
import json
import os
import re
import sys
from collections import Counter
from datetime import date, datetime, timezone

import requests

from common import ROOT, load_config, load_fits, save_fits, validate
from dedupe import same

STATUS = ROOT / "data" / "status.json"
MODEL = os.environ.get("LEADS_MODEL", "").strip() or "claude-sonnet-5-5"
API = "https://api.anthropic.com/v1/messages"


def record(result, message, **extra):
    try:
        st = json.loads(STATUS.read_text()) if STATUS.exists() else {}
    except ValueError:
        st = {}
    st["leads"] = {"last_run": datetime.now(timezone.utc).isoformat(timespec="seconds"), "result": result, "message": message, **extra}
    STATUS.write_text(json.dumps(st, indent=1) + "\n")


def context(doc, cfg):
    fits = doc["fits"]
    on_file = "\n".join(f"- {f['celeb']} | {f['context']} | {f['date']} | {f['status']}" for f in sorted(fits, key=lambda f: f["celeb"]))
    recent = sorted(fits, key=lambda f: -int(f["find"]))[:20]
    mix = Counter(f["category"] for f in recent)
    waiting = sum(1 for f in fits if f["status"] == "review")
    return on_file, mix, waiting


SCHEMA = """Return ONLY a JSON array (inside ```json fences) of lead objects, best first, each like:
{"celeb": "...", "context": "event", "date": "Oct 12, 2026", "category": "Fit|Kicks|Wrist",
 "headline": "<=60 chars", "detail": "1-2 sentences in your own words", "tags": ["nfl"],
 "sources": [{"label": "Outlet — article", "url": "https://..."}],
 "items": [{"label": "Exact|Similar", "type": "watch|sneakers|shoes|clothing|bag|jewelry|accessory", "brand": "...", "name": "...",
            "product_url": "https://... or empty", "retailer": "key or empty", "query": "search words or empty",
            "image_src": "direct product image URL you saw, or empty", "note": ""}],
 "photo_options": [{"image": "direct image URL of the person in this outfit", "page": "page it's on", "credit": "photographer / outlet"}],
 "photo_leads": [{"kind": "instagram|video|photo", "url": "https://...", "by": "@account or outlet", "at": "0:42", "note": ""}],
 "photo_source": "article url",
 "score": 0-100, "score_parts": {"shop": 0-40, "star": 0-25, "cover": 0-20, "fresh": 0-15}, "score_note": "one line", "note": ""}
Every item needs either product_url, or retailer + query (retailer must be one of the keys listed), or note "Custom piece — not for sale".
If nothing worth adding turned up, return []."""


def ask(prompt, key):
    """Run Claude with web search until it finishes (server tools can pause long turns)."""
    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 25}]
    text = ""
    for _ in range(8):
        r = requests.post(API, timeout=600, headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                          json={"model": MODEL, "max_tokens": 16000, "messages": messages, "tools": tools})
        if r.status_code >= 400:
            raise RuntimeError(f"Anthropic API {r.status_code}: {r.text[:300]}")
        body = r.json()
        text += "".join(b.get("text", "") for b in body.get("content", []) if b.get("type") == "text")
        if body.get("stop_reason") == "pause_turn":  # long search session: hand the turn back and let it continue
            messages.append({"role": "assistant", "content": body["content"]})
            continue
        return text
    return text


def parse(text):
    m = re.findall(r"```json\s*(\[.*?\])\s*```", text, re.S) or re.findall(r"(\[\s*\{.*\}\s*\])", text, re.S)
    if not m:
        raise ValueError("Claude didn't return a JSON list of leads.")
    return json.loads(m[-1])


def main():
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        record("error", "Add the ANTHROPIC_API_KEY repo secret to use Find leads (GitHub → Settings → Secrets and variables → Actions).")
        sys.exit("ANTHROPIC_API_KEY is not set.")
    cfg, doc = load_config(), load_fits()
    on_file, mix, waiting = context(doc, cfg)
    count = os.environ.get("COUNT", "").strip()
    focus = os.environ.get("FOCUS", "").strip()
    rules = (ROOT / "LEADS.md").read_text()
    events = (ROOT / "data" / "events.json").read_text()
    prompt = f"""Today is {date.today():%A, %B %d, %Y}. You are the lead finder for Cop the Fit (celebrity men's fits, identified, with affiliate links).
Follow these rules exactly (ignore the parts about running scripts, editing files and committing: this program does that):

{rules}

Season calendar (data/events.json):
{events}

How many leads: {f"exactly up to {count}" if count else "decide from the calendar per the rules"}. Leads already waiting for review: {waiting}.
{f"Niral asked to focus on: {focus}" if focus else ""}
Category mix of the last 20 fits: {dict(mix)} (target ~40% Kicks, 30% Fit, 30% Wrist).
Retailer keys you may use for retailer + query: {", ".join(cfg["retailers"])}.

Already on file (person | event | date | status). Never return any of these again, in any wording:
{on_file}

Search the web, verify every item against its source, then answer.
{SCHEMA}"""
    try:
        leads = parse(ask(prompt, key))
    except Exception as e:  # noqa: BLE001
        record("error", f"Lead search failed: {str(e)[:250]}")
        raise
    added, skipped = [], []
    nxt = max(int(f["find"]) for f in doc["fits"]) + 1 if doc["fits"] else 1
    for raw in leads:
        lead = {k: v for k, v in raw.items() if k in {"celeb", "context", "date", "category", "headline", "detail", "tags", "sources", "items",
                                                       "photo_leads", "photo_options", "photo_source", "score", "score_parts", "score_note", "note"}}
        lead.update(find=f"{nxt:03d}", status="review", ig_queue=False, priority=1, added=date.today().isoformat(), timing="Recent",
                    posted_at=None, ig_media_id=None, ig_permalink=None)
        lead.setdefault("note", "")
        lead.setdefault("tags", [])
        for n, it in enumerate(lead.get("items", []), start=2):
            it["slide"] = n
            for k in ("brand", "product_url", "retailer", "query", "note"):
                it.setdefault(k, "")
            if not it.get("image_src"):
                it.pop("image_src", None)
            if it.get("retailer") and it["retailer"] not in cfg["retailers"]:
                it["retailer"], it["query"] = "", ""
            if not (it["product_url"] or (it["retailer"] and it["query"])):
                it["note"] = it["note"] or "Custom piece — not for sale"
        dup = next((f for f in doc["fits"] if same(f, lead)), None)
        if dup:
            skipped.append(f"{lead.get('celeb')} ({lead.get('context')}): repeat of #{dup['find']}")
            continue
        trial = {"fits": doc["fits"] + [lead]}
        errs = [e for e in validate(trial, cfg) if e.startswith(lead["find"])]
        if errs:
            skipped.append(f"{lead.get('celeb')}: {errs[0]}")
            continue
        doc["fits"].append(lead)
        added.append(lead)
        nxt += 1
    save_fits(doc)
    msg = (f"Found {len(added)} new lead{'s' if len(added) != 1 else ''}" + (f", skipped {len(skipped)}" if skipped else "") + "."
           if added else ("No new leads worth adding right now." + (f" Skipped {len(skipped)}." if skipped else "")))
    record("ok", msg, added=[f"#{f['find']} {f['celeb']} ({f.get('score', '?')})" for f in added], skipped=skipped[:10])
    print(msg)
    for f in added:
        print(f"  #{f['find']} {f.get('score')} {f['celeb']}: {f['headline']}")
    for s in skipped:
        print("  skipped:", s)


if __name__ == "__main__":
    main()
