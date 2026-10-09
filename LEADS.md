# Lead finder instructions

The scheduled Claude run follows this file twice a week. Edit it to change what gets found.

## Goal
Add 4–8 new male-celebrity fits from the last 7 days to `data/fits.json` as `"status": "review"`, so they show up in the Chrome extension's Review tab. Quality beats quantity: skip anything you can't verify.

## Where to look
- NFL arrivals: NFL.com "The Fit Files", ESPN/ABC "best arrivals" recaps (in season, Mon–Tue)
- NBA tunnel fits: LeagueFits coverage, The GAME (thegame.ph), Complex (in season)
- Red carpets and events: watch-spotting posts (Watch Guys, Luxury Bazaar, Teddy Baldassarre, Avi & Co, Precision Watches), red-carpet recaps (GQ, Esquire, HOLA!, Vogue)
- Sneakers and style news: GQ, Highsnobiety, UpscaleHype, Hypebeast, Complex Style
- Search ideas: "[celebrity] wore", "best dressed men this week", "watch spotting [event]", "tunnel fit"

## Rules for each fit
1. **Verify.** Open the article and confirm every item (brand, model, reference) is stated there. Drop items the article doesn't name. Never mix up who wore what.
2. **Skip duplicates.** Same person + same event already in the file means skip.
3. **Write in your own words.** `headline` ≤ 60 characters, punchy, no clickbait claims the source doesn't support. `detail` is 1–2 sentences. No quotes longer than a few words.
4. **Items (1–8):**
   - `Exact`: what the article names. Set `brand`, `name`, and either `product_url` (a real retailer product page you found) or `retailer` + `query` (a retailer key from `config.json` → `retailers`). Watches: `chrono24`. Luxury fashion: `farfetch`. Resale/sold out: `ebay`, `stockx`, `goat`.
   - `Similar`: 1–2 cheaper, buyable look-alikes, usually `amazon` + a plain search query. Never use the words dupe, fake, faux or replica.
   - One-off/custom pieces: no retailer, `note: "Custom piece — not for sale"`, plus a Similar pick.
   - `slide` numbers start at 2 and go up by 1.
5. **Product images (`image_src`):** for every item, set `image_src` to a direct image URL of a clean studio product shot, so all slides look consistent: plain white or light background, product only (no box, hanger, hands, model or lifestyle scene), whole product visible. Watches: dial facing front. Sneakers: side profile, one shoe. Clothing: flat or ghost-mannequin front.
   Source order: the brand's official store → StockX or GOAT → Farfetch, SSENSE, Mr Porter, END. or an authorized dealer. Never eBay seller photos, press/agency photos, or anything watermarked. Only use a URL you actually saw on the page. The image must show the same model as the item; if only a different version exists, leave `image_src` empty rather than show the wrong product.
6. **Where to grab the cover (`photo_leads`):** Niral screenshots the cover himself, so list 1–3 places that clearly show the outfit, best first:
   1. The celebrity's own Instagram post of the look (`instagram.com/p/…` or `/reel/…`).
   2. A video from the celebrity, team, league or event: YouTube, TikTok, or an Instagram reel (tunnel walks, arrival clips, vlogs, GRWM). Add `at` with the timestamp where the full outfit is clearest (e.g. "0:42").
   3. The team's, league's or event's official Instagram post.
   Each lead is `{"kind": "instagram" | "video", "url": "…", "by": "@account or channel", "at": "0:42", "note": "optional"}`. Never list Getty, Backgrid, Shutterstock, AP or other agency photos or footage, or anything watermarked. Only list links you actually found; if none, leave `photo_leads` empty. Keep `photo_source` as the article link.
7. **Fields:** `find` (next free 3-digit number), `status: "review"`, `priority: 0`, `added` (today, YYYY-MM-DD), `celeb`, `context` (event), `date` (e.g. "Oct 12, 2026"), `category` (Fit, Kicks or Wrist), `timing: "Recent"`, `tags` (1–2 lowercase hashtags like "nfl", "tunnelfit"), `sources` ([{label: "Outlet — article", url}]), `note`, `posted_at: null`, `ig_media_id: null`, `ig_permalink: null`.

## Finish
1. Run `python scripts/check.py` and fix any errors.
2. Commit only `data/fits.json` with the message `Leads: #NNN–#NNN` and push to `main`.
3. Reply with a short list: Find #, who, headline, item count, source.
