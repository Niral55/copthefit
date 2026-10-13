# Cop the Fit — instructions for AI assistants (ChatGPT/Codex and others)

Celebrity men's fits identified, with affiliate links. Owner: Niral. Live site: https://niral55.github.io/copthefit (admin at /admin.html).
Another assistant (Claude) also works on this repo, so read these rules first. They are the same rules it follows (see CLAUDE.md).

## Rules
- Finding leads: follow LEADS.md exactly, starting with its Non-negotiables. Don't change the rules.
- Run `python scripts/check.py` before committing. It enforces affordable-only, product image, person photo, no-watermark and public-note rules.
- Item `note` fields are shown publicly on the site. Never put research notes there (use the lead's top-level `note`).
- Look at every image before using it.
- Don't edit individual live listings unless Niral asks; he edits those himself in the admin page.
- Save data/fits.json with the repo's format (json indent=1, `scripts/common.py` → `save_fits`), so diffs stay small.
- Pushing to `main` deploys the site (GitHub Actions, ~3 min). Pull right before you push; the build bot also commits to main.
- Prefer a branch + pull request for code or design changes so Niral can review them; data-only lead additions can go straight to main.
- Never add tokens, passwords or API keys to the repo. Secrets live in GitHub Actions settings.

## Map
- `data/fits.json` — every listing (status: approved/posted = live, review = lead, rejected = unpublished)
- `data/videos.json` + `VIDEOS.md` — video groups and scripts; `scripts/make_video.py` renders them (workflow: Make video)
- `templates/site.html` — public site; `templates/admin.html` — admin page; `scripts/build_site.py` — builds `dist/`
- `LEADS.md` — how to find leads; `scripts/check.py` — data checks
