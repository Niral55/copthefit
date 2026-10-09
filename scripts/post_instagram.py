"""Publish the next carousel in the queue to Instagram (Instagram API with Instagram Login).

Needs repo secrets IG_USER_ID and IG_ACCESS_TOKEN. Slides must already be live on the site
(the build workflow renders and deploys them), because Instagram fetches each JPEG by URL.

Env: DRY_RUN=true prints what would be posted. IG_API_VERSION (optional, e.g. v26.0).
"""
import os
import sys
import time
from datetime import datetime, timezone

import requests

import json

from common import ROOT, load_config, load_fits, save_fits, queue, ready_queue, caption, ig_items

STATUS = ROOT / "data" / "status.json"


def record(result, message, **extra):
    """Leave a note for the admin page: is Instagram connected, and what happened on the last run."""
    try:
        st = json.loads(STATUS.read_text()) if STATUS.exists() else {}
    except ValueError:
        st = {}
    st["instagram"] = {"connected": bool(os.environ.get("IG_USER_ID") and os.environ.get("IG_ACCESS_TOKEN")),
                       "last_run": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "result": result, "message": message, **extra}
    STATUS.write_text(json.dumps(st, indent=1) + "\n")


def api(path):
    ver = os.environ.get("IG_API_VERSION", "").strip()
    return f"https://graph.instagram.com/{ver + '/' if ver else ''}{path}"


def call(method, path, **params):
    params["access_token"] = os.environ["IG_ACCESS_TOKEN"]
    r = requests.request(method, api(path), data=params if method == "POST" else None,
                         params=params if method == "GET" else None, timeout=60)
    body = r.json() if r.headers.get("content-type", "").startswith(("application/json", "text/javascript")) else {}
    if r.status_code >= 400 or "error" in body:
        sys.exit(f"Instagram API error on {path}: {body.get('error', r.text)}")
    return body


def main():
    cfg = load_config()
    if cfg.get("posting_paused"):
        print("posting_paused is true in config.json; nothing posted.")
        record("paused", "Auto-posting is paused.")
        return
    doc = load_fits()
    want = os.environ.get("FIND", "").strip().zfill(3) if os.environ.get("FIND", "").strip() else ""
    q = ready_queue(doc, cfg)
    if want:
        q = [f for f in doc["fits"] if f["find"] == want and f["status"] == "approved"]
        if not q:
            sys.exit(f"#{want} isn't approved (or doesn't exist), so it can't be posted.")
    if not q:
        waiting = len(queue(doc))
        msg = (f"Nothing ready to post. {waiting} queued posts are waiting for a cover photo." if waiting
               else "Instagram queue is empty: add posts to it in the admin to keep posting.")
        print(msg)
        record("empty", msg)
        return
    fit = q[0]
    site = cfg["site_url"].rstrip("/")
    n = len(ig_items(fit)) + 2
    urls = [f"{site}/slides/{fit['find']}/{i:02d}.jpg" for i in range(1, n + 1)]
    text = caption(cfg, fit)
    print(f"Next: #{fit['find']} {fit['celeb']} ({n} slides, {len(q)} in queue)")

    dry = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
    if not dry and not (os.environ.get("IG_USER_ID") and os.environ.get("IG_ACCESS_TOKEN")):
        print("IG_USER_ID / IG_ACCESS_TOKEN secrets aren't set yet; nothing posted.")
        record("not_connected", f"Instagram isn't connected, so #{fit['find']} wasn't posted.")
        return

    if want:  # posted right after an edit: wait until the rebuilt slides are live
        stamp_url = f"{site}/slides/{fit['find']}/stamp.txt"
        for _ in range(30):
            r = requests.get(stamp_url, timeout=30, params={"t": time.time()})
            if r.status_code == 200 and r.text.strip() == fit.get("updated", ""):
                break
            print("Waiting for the new slides to go live…")
            time.sleep(30)
        else:
            sys.exit("The rebuilt slides didn't go live within 15 minutes. Check the Build and deploy run.")

    missing = [u for u in urls if requests.head(u, timeout=30, allow_redirects=True).status_code != 200]
    if missing:
        sys.exit("Slides aren't live yet (run the Build and deploy workflow first): " + ", ".join(missing))

    if dry:
        record("dry_run", f"Preview only: #{fit['find']} would post next.")
        print("DRY RUN, nothing posted.\n" + "\n".join(urls) + "\n---\n" + text)
        return

    user = os.environ["IG_USER_ID"]
    children = [call("POST", f"{user}/media", image_url=u, is_carousel_item="true")["id"] for u in urls]
    parent = call("POST", f"{user}/media", media_type="CAROUSEL", children=",".join(children), caption=text)["id"]
    for _ in range(20):  # up to ~5 minutes
        status = call("GET", parent, fields="status_code").get("status_code")
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            sys.exit(f"Instagram couldn't process the carousel (status {status}).")
        time.sleep(15)
    else:
        sys.exit("Timed out waiting for Instagram to process the carousel.")
    media_id = call("POST", f"{user}/media_publish", creation_id=parent)["id"]
    link = call("GET", media_id, fields="permalink").get("permalink", "")

    fit["status"] = "posted"
    fit["ig_queue"] = False
    fit["posted_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    fit["ig_media_id"] = media_id
    fit["ig_permalink"] = link
    save_fits(doc)
    record("posted", f"Posted #{fit['find']} {fit['celeb']}.", find=fit["find"], permalink=link)
    print(f"Posted #{fit['find']}: {link}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:  # a failed post: tell the admin why
        if e.code not in (None, 0):
            record("error", str(e.code)[:300])
        raise
