"""Keep the Instagram token alive. Long-lived tokens last 60 days; refreshing resets the clock.

If Instagram hands back a different token string and a GH_PAT secret exists (a token that can
write repo secrets), the IG_ACCESS_TOKEN secret is updated automatically.
"""
import os
import subprocess
import sys

import requests


def main():
    tok = os.environ.get("IG_ACCESS_TOKEN")
    if not tok:
        print("No IG_ACCESS_TOKEN secret yet; skipping refresh.")
        return
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": tok}, timeout=30)
    body = r.json()
    if "access_token" not in body:
        sys.exit(f"Token refresh failed: {body.get('error', body)}. "
                 "If the token expired, generate a new one in the Meta app dashboard and update the secret.")
    days = int(body.get("expires_in", 0)) // 86400
    print(f"Token refreshed, valid for {days} more days.")
    new = body["access_token"]
    if new != tok:
        pat = os.environ.get("GH_PAT")
        if not pat:
            print("::warning::Instagram issued a new token string. Add a GH_PAT secret so it can be saved automatically, "
                  "or paste the new token into the IG_ACCESS_TOKEN secret within 60 days.")
            return
        subprocess.run(["gh", "secret", "set", "IG_ACCESS_TOKEN", "--repo", os.environ["GITHUB_REPOSITORY"], "--body", new],
                       check=True, env={**os.environ, "GH_TOKEN": pat})
        print("Saved the new token to the IG_ACCESS_TOKEN secret.")


if __name__ == "__main__":
    main()
