# Lead finder instructions

Claude follows this file whenever you press **Find leads** in the admin page (it runs on GitHub with the Anthropic API; nothing is scheduled). Edit it to change what gets found.

## Goal
Cop the Fit makes money from affiliate sales. Find male-celebrity fits that people will **buy from**, fast enough to catch the spike right after the event, and add them to `data/fits.json` as leads (`"status": "review"`) for Niral to finish in the admin page's Leads tab. Quality beats quantity: skip anything you can't verify.

## 0. Plan today's run
1. Open `data/events.json` and see what happened **yesterday or over the weekend** (NFL Sunday → Monday, Monday/Thursday Night Football → next day, award shows → next morning, fashion weeks and tournaments → daily).
   - Event morning: aim for the event's `volume` (up to 8).
   - Ordinary day: aim for 2–4.
2. Count the leads already waiting (`"status": "review"`). If 15 or more are waiting, add **at most 2**, the highest-scoring only. Leads pile up faster than they get finished otherwise.
3. Run `python scripts/dedupe.py` and read the list. It's every person + event already on file, in any status (including unpublished ones Niral turned down). Never add those again.
4. Check the category mix of the last 20 fits (`category`): aim for about 40% Kicks (sneakers and streetwear), 30% Fit, 30% Wrist. When two leads score about the same, take the one in the category that's behind.

## 1. Where to look
- NFL arrivals: NFL.com "The Fit Files", team Instagram/TikTok arrival posts, ESPN/ABC "best arrivals", LeagueFits
- NBA tunnel fits: LeagueFits, team Instagram tunnel posts, Complex, The GAME (thegame.ph)
- Red carpets and events: watch-spotting posts (Watch Guys, Luxury Bazaar, Teddy Baldassarre, Avi & Co, Precision Watches), red-carpet recaps (GQ, Esquire, Vogue, HOLA!)
- Sneakers and streetwear on celebs: Hypebeast, Highsnobiety, UpscaleHype, Sole Retriever, Complex Sneakers
- The event's `sources` in `data/events.json`
- Search ideas: "[celebrity] wore", "[event] best dressed men", "watch spotting [event]", "tunnel fit [team]", "[celebrity] sneakers"

## 2. Before researching a candidate
Run `python scripts/dedupe.py "Name" "Event" "Date"`. If it prints DUPLICATE, drop it and move on.

## 3. Skip the lead (hard filters)
Skip it if **any** of these is true:
- **Nothing to buy.** No Exact piece is buyable from a store with an affiliate program (Amazon, eBay, StockX, GOAT, Farfetch, SSENSE, Nike, adidas, New Balance, Converse, Chrono24, Jomashop, brand stores via Skimlinks…) **and** there's no strong cheaper pick. Custom one-offs alone don't earn.
- **No cover.** You can't find any clear photo or video of the look anywhere (see 6).
- **Can't verify.** The source doesn't name the pieces, or it's unclear who wore what.
- **Low pull.** Men 18–34 in the US wouldn't recognize the person: not a current NFL/NBA/MLB/soccer name, a rapper or musician with mainstream reach, or a well-known actor.

## 4. Score every lead (0–100)
Set `score` (the total), `score_parts` and a one-line `score_note`. Niral's Leads tab is sorted by score.

| Part | Points | How |
|---|---|---|
| `shop` | 0–40 | 40: Exact sneakers or streetwear under ~$500, in stock at StockX/GOAT/Nike/Amazon etc. 30: Exact pieces $500–$2,500 buyable through an affiliate store, or a pricey Exact piece plus a solid cheaper pick. 20: luxury pieces only resale or Chrono24/eBay. 10: mostly cheaper picks. |
| `star` | 0–25 | 25: household name for young men (Travis Scott, Drake, LeBron, Mahomes, Bad Bunny, A$AP Rocky…). 15: well-known starter or headliner. 8: niche. |
| `cover` | 0–20 | 20: the celeb's own Instagram post or a clear video. 15: team/league/event post. 10: a clear editorial/press photo. 0: nothing (skip the lead). |
| `fresh` | 0–15 | 15: event within 24 hours. 12: within 48 hours. 6: within a week. 2: older (evergreen only). |

Example: `"score": 82, "score_parts": {"shop": 40, "star": 25, "cover": 15, "fresh": 2}, "score_note": "Jordan 4s in stock on StockX; Travis Scott; team tunnel video"`.

## 5. Rules for each fit
1. **Verify.** Open the article and confirm every item (brand, model, reference) is stated there. Drop items the article doesn't name. Never mix up who wore what.
2. **Write in your own words.** `headline` ≤ 60 characters, punchy, no clickbait claims the source doesn't support. `detail` is 1–2 sentences. No quotes longer than a few words.
3. **Items (1–8):**
   - `Exact`: what the article names. Set `brand`, `name`, and either `product_url` (a real retailer product page you found, best: one that pays commission) or `retailer` + `query` (a retailer key from `config.json` → `retailers`). Watches: `chrono24`. Luxury fashion: `farfetch`. Resale/sold out: `stockx`, `goat`, `ebay`.
   - `Similar`: 1–2 cheaper, buyable look-alikes, usually `amazon` + a plain search query. **Only when the exact piece is expensive (roughly over $250) or sold out.** Don't add a "get it for less" pick for something that's already affordable (Fossil, Seiko 5, Casio, Nike/adidas/New Balance general releases, etc.). Similar picks are also fine for pieces of the outfit the source didn't name. Never use the words dupe, fake, faux or replica.
   - Every item gets a `type`: watch, sneakers, shoes, clothing, bag, jewelry or accessory (the site's Kicks/Wrist filters use it).
   - One-off/custom pieces: no retailer, `note: "Custom piece — not for sale"`, plus a Similar pick.
   - `slide` numbers start at 2 and go up by 1.
4. **Product images (`image_src`):** for every item, set `image_src` to a direct image URL of a clean studio product shot, so all slides look consistent: plain white or light background, product only (no box, hanger, hands, model or lifestyle scene), whole product visible. Watches: dial facing front. Sneakers: side profile, one shoe. Clothing: flat or ghost-mannequin front.
   Source order: the brand's official store → StockX or GOAT → Farfetch, SSENSE, Mr Porter, END. or an authorized dealer. Never eBay seller photos or anything watermarked. Only use a URL you actually saw on the page. The image must show the same model as the item; if only a different version exists, leave `image_src` empty rather than show the wrong product.
5. **Where to grab the cover (`photo_leads`):** Niral picks the cover and edits it himself, so list 1–3 of the **clearest full-length shots of the look**, best first. Any source is fine: the celeb's or team's Instagram, a video (YouTube, TikTok, reels) with the timestamp in `at`, or a press/editorial photo page (Getty, the article itself, etc.). Prefer full-length, sharp, well-lit and unwatermarked versions; if the best one is watermarked, say so in `note`.
   Each lead is `{"kind": "instagram" | "video" | "photo", "url": "…", "by": "@account, channel or outlet", "at": "0:42", "note": "optional"}`. Only list links you actually found. Keep `photo_source` as the article link.
6. **Fields:** `find` (next free 3-digit number), `status: "review"`, `ig_queue: false`, `added` (today, YYYY-MM-DD), `celeb`, `context` (event), `date` (as exact as you know it, e.g. "Oct 12, 2026"; the site works out Recent/Evergreen from it), `category` (Fit, Kicks or Wrist), `tags` (1–2 lowercase hashtags like "nfl", "tunnelfit"), `sources` ([{label: "Outlet — article", url}]), `score`, `score_parts`, `score_note`, `note`, `posted_at: null`, `ig_media_id: null`, `ig_permalink: null`.

## 6. Finish
1. Run `python scripts/check.py`. It fails on repeats and on leads without a score: fix or remove those, then run it again until it passes.
2. Commit only `data/fits.json` with the message `Leads: #NNN–#NNN` and push to `main`.
3. Reply with a short list, highest score first: Find #, score, who, headline, why it should sell, source.
