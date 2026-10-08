# Cop the Fit

Celebrity fits, identified. One data file (`data/fits.json`) drives the site, the Instagram carousels and the posting queue.

```
Lead finder (Claude, Mon + Thu)  →  Review in the Chrome extension  →  Approve
        ↓                                                               ↓
Right-click product images  →  images/inbox  →  Build workflow: cut out images, render slides, rebuild site
                                                                        ↓
                                        Daily post workflow (12:05 PM ET): next carousel → Instagram
```

## Admin page: `<site>/admin.html`

Your control panel, on a computer or phone. Connect it once (Settings: GitHub username + token).

- **Leads**: fits the lead finder found. Open one, add the cover photo (upload, paste, or tap a free photo), click the photo to pin each item, add product images and shop links, then **Save & add to queue**, **Post next** or **Post now**.
- **Queue**: approved posts in posting order, with what each still needs (photo, images, links).
- **Posted**: live posts. Edits update the site.
- **Unpublished**: hidden posts. Open one to restore it.
- **+ New post**: the same editor, empty.

Post now needs the token to also have **Actions: Read and write**. It waits for the new slides to build, then posts (about 5 minutes).

## Day to day (about an hour a week)

| Job | Where | Time |
|---|---|---|
| Finish and approve new leads | Admin page → **Leads** | 2 min each |
| Approve or reject new fits (from Chrome) | Extension → **Review** | 1 min each |
| Add the cover photo | Right-click the photo of the look → **Cop the Fit: set as cover photo** → pick Find #, add the credit, click to pin each item (optional) | 30 sec each |
| Add product images | Right-click a product shot on a shop page → **Cop the Fit: add product image** → pick Find # and item | 10 sec each |
| Add a fit you spotted | Extension → **Add fit** | 2 min |
| Pause posting | `config.json` → `"posting_paused": true` | |

Free cover photos are found automatically: every build searches Wikimedia Commons for public-domain and Creative Commons photos (commercial use allowed) taken the day of the event, and uses one with the credit filled in. Same-month matches show up as "free photo" links in the Queue tab for you to check.

On the site, every listing has image slots. Product cutouts fill the item thumbnails as you add them. The photo of the look shows on the site only when it's free-licensed (`"site_photos": "free"`); set it to `"all"` to show every cover photo or `"none"` for none. Empty slots show a "Photo coming" placeholder.

With `"require_photo": true` (the default), the daily job only posts fits that have a cover photo and skips the rest until you add one. The extension's Queue tab lists the next fits that still need one, with a link to the photo the lead finder found.

Everything else runs on its own. Each change rebuilds the site and slides in about 3 minutes.

## One-time setup

### 1. Site (GitHub Pages)
1. The build publishes the site to the `gh-pages` branch. If the site doesn't appear, open repo → **Settings → Pages** and set Source to **Deploy from a branch → gh-pages / (root)**.
2. In `config.json` set `site_url` to `https://<your-username>.github.io/copthefit` and `instagram_handle`.
3. Repo → **Actions** → **Build and deploy** → **Run workflow**. The site is live when it turns green.
4. Own domain later: set `custom_domain` in `config.json` and add the domain under Settings → Pages.

### 2. Chrome extension
1. Download this repo (Code → Download ZIP) and unzip it.
2. `chrome://extensions` → turn on **Developer mode** → **Load unpacked** → pick the `extension` folder.
3. Make a token: GitHub → Settings → Developer settings → **Fine-grained tokens** → Generate. Repository access: **Only select repositories → copthefit**. Permissions → Repository → **Contents: Read and write**.
4. Click the extension icon → **Settings**: your username, `copthefit`, `main`, the token, your site URL → **Save and test**.

### 3. Instagram auto-posting
1. Instagram app → Settings → Account type → switch to a **Professional** account (Creator or Business).
2. Go to [developers.facebook.com](https://developers.facebook.com/apps) → **Create app** → pick the Instagram use case (managing content on Instagram).
3. In the app: **Instagram → API setup with Instagram login** → **Generate access tokens** → add your Instagram account → log in → copy the **token** and the **Instagram user ID** shown there. Exact labels move around; you want a long-lived token with `instagram_business_basic` and `instagram_business_content_publish`.
4. Repo → **Settings → Secrets and variables → Actions → New repository secret**:
   - `IG_USER_ID`: the numeric user ID
   - `IG_ACCESS_TOKEN`: the token
   - Optional `GH_PAT`: a fine-grained token on this repo with **Secrets: Read and write**. Lets the daily job save a refreshed Instagram token by itself. Without it, the job warns you when to paste a new one.
5. Test: Actions → **Daily Instagram post** → Run workflow with **Preview only** checked. It prints the slides and caption. Run it unchecked to post for real. After that it posts every day on its own.

Your own account works without Meta App Review.

### 4. Affiliate links
Put your IDs in `config.json` → `affiliate`, commit, and every link on the site updates:
- `amazon_tag`: Amazon Associates tracking ID (also list the site and Instagram in Associates Central)
- `ebay_campaign_id`: eBay Partner Network campaign ID
- `skimlinks_id` (or `sovrn_key`): wraps every other retailer link

### 5. Comment-to-DM (optional)
Set up ManyChat: keyword **FIT** on any post → DM "Every link is here: <site_url>, search the Find # from the post." Then set `"comment_keyword": "FIT"` in `config.json`. Captions and the last slide switch to "Comment FIT".

## Files

| Path | What it is |
|---|---|
| `data/fits.json` | Every fit: status (`review`, `approved`, `posted`, `rejected`), items, sources |
| `config.json` | Site URL, handle, affiliate IDs, retailers |
| `images/inbox/` | Raw product images land here (from the extension or upload as `003-2.jpg`) |
| `images/cut/` | Background-removed cutouts used on slides and the site |
| `images/photos/` | Cover photos of each look (`003.jpg`), with credit and item pins stored in `data/fits.json` |
| `templates/` | `site.html` and `slide.html` (the carousel design) |
| `scripts/` | `check.py`, `process_images.py`, `render_slides.py`, `build_site.py`, `post_instagram.py`, `refresh_token.py` |
| `LEADS.md` | Instructions the lead-finder run follows |
| `extension/` | Cop the Fit Studio Chrome extension |

## Run locally
```
pip install -r requirements.txt && python -m playwright install chromium
python scripts/check.py && python scripts/process_images.py && python scripts/render_slides.py && python scripts/build_site.py
open dist/index.html
```

## Posting order
Approved fits post one a day. Fits marked "post next" (priority 0) go first, then the rest by Find #. Instagram allows 10 slides per carousel, so a fit has at most 8 items (cover + items + final slide).
