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
5. **Photo of the look:** set `photo_source` to the best page showing the outfit, so Niral can right-click the photo into the cover. Prefer, in order: the celebrity's own Instagram post, the team's or event's official post, then the article. Pick a clear, full-length shot without a watermark.
6. **Fields:** `find` (next free 3-digit number), `status: "review"`, `priority: 0`, `added` (today, YYYY-MM-DD), `celeb`, `context` (event), `date` (e.g. "Oct 12, 2026"), `category` (Fit, Kicks or Wrist), `timing: "Recent"`, `tags` (1–2 lowercase hashtags like "nfl", "tunnelfit"), `sources` ([{label: "Outlet — article", url}]), `note`, `posted_at: null`, `ig_media_id: null`, `ig_permalink: null`.

## Finish
1. Run `python scripts/check.py` and fix any errors.
2. Commit only `data/fits.json` with the message `Leads: #NNN–#NNN` and push to `main`.
3. Reply with a short list: Find #, who, headline, item count, source.
