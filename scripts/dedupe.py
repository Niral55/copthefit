"""Stop repeat leads. A new fit is a duplicate of one we already have (in ANY status, including
unpublished/rejected ones, so turned-down leads don't come back) when it's the same person and:
  - the same event (same normalized context), or
  - an event date within 3 days, or
  - the same source article, or
  - the same exact piece (brand + name).

Usage:
  python scripts/dedupe.py                       # list every person + event we already have (read before searching)
  python scripts/dedupe.py "Travis Scott" "US Open" "Aug 31, 2026"   # is this one new?
check.py runs the same test on every lead in data/fits.json and fails if one is a repeat.
"""
import re
import sys
import unicodedata

from common import load_fits

STOP = {"heading", "spotted", "the", "a", "an", "of", "at", "to", "in", "on", "for", "and", "arrival", "arrivals", "night", "game", "red", "carpet",
        "premiere", "awards", "award", "show", "week", "nfl", "nba", "fit", "outfit", "look", "out", "off", "duty"}


def norm(t):
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower().replace("$", "s")
    return re.sub(r"[^a-z0-9 ]+", " ", t).strip()


def person(t):
    return re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", norm(t)).replace(" ", "")


def event_words(t):
    return {w for w in norm(t).split() if w not in STOP and not re.fullmatch(r"(19|20)\d\d", w)}


def when(fit):
    from build_site import event_date  # same date parser the site uses
    return event_date(fit.get("date"))


def same(a, b):
    """Why b repeats a ("" if it doesn't)."""
    if person(a.get("celeb")) != person(b.get("celeb")):
        return ""
    da, db = when(a), when(b)
    wa, wb = event_words(a.get("context")), event_words(b.get("context"))
    overlap = len(wa & wb) / min(len(wa), len(wb)) if wa and wb else 0
    if overlap >= 0.6 and (not da or not db or abs((da - db).days) <= 45):
        return "same event"
    if da and db and abs((da - db).days) <= 3 and "-" not in (a.get("date", "") + b.get("date", "")):
        exact_dates = re.search(r"\d{1,2},", a.get("date", "")) and re.search(r"\d{1,2},", b.get("date", ""))
        if exact_dates:
            return "same week of events"
    ua = {s.get("url", "").split("?")[0].rstrip("/") for s in a.get("sources", []) if s.get("url")}
    ub = {s.get("url", "").split("?")[0].rstrip("/") for s in b.get("sources", []) if s.get("url")}
    if ua & ub:
        return "same source article"
    ia = {norm(i.get("brand", "") + " " + i["name"]) for i in a.get("items", []) if i.get("label") == "Exact"}
    ib = {norm(i.get("brand", "") + " " + i["name"]) for i in b.get("items", []) if i.get("label") == "Exact"}
    if ia & ib and wa & wb:
        return "same piece at a similar event"
    return ""


def duplicates(doc):
    """[(new_fit, older_fit, reason)] for every lead that repeats an earlier fit."""
    out = []
    fits = sorted(doc["fits"], key=lambda f: int(f["find"]))
    for i, b in enumerate(fits):
        for a in fits[:i]:
            why = same(a, b)
            if why:
                out.append((b, a, why))
                break
    return out


def main():
    doc = load_fits()
    if len(sys.argv) > 1:
        cand = {"celeb": sys.argv[1], "context": sys.argv[2] if len(sys.argv) > 2 else "", "date": sys.argv[3] if len(sys.argv) > 3 else "", "items": [], "sources": []}
        hits = [(f, same(f, cand)) for f in doc["fits"] if same(f, cand)]
        if hits:
            for f, why in hits:
                print(f"DUPLICATE ({why}): #{f['find']} {f['celeb']} · {f['context']} · {f['date']} [{f['status']}]")
            sys.exit(1)
        print("new")
        return
    for f in sorted(doc["fits"], key=lambda f: (person(f["celeb"]), f.get("date", ""))):
        print(f"{f['celeb']} | {f['context']} | {f['date']} | #{f['find']} {f['status']}")


if __name__ == "__main__":
    main()
