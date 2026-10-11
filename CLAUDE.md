# Cop the Fit

Celebrity men's fits identified, with affiliate links. Owner: Niral. Live site: https://niral55.github.io/copthefit (admin at /admin.html).

## Finding leads
When Niral asks for leads, follow **LEADS.md exactly**, starting with its Non-negotiables. Don't change the rules on your own.
Leads are run from chat (no API key, nothing scheduled). Run `python scripts/check.py` before committing; it enforces the
affordable-only, product-image, person-photo, no-watermark and public-note rules for new leads.

## Working rules
- Item `note` is shown publicly. Never put research notes there.
- Look at every image before using it (have the build download it, then view the file).
- Don't edit individual live listings unless Niral asks; he edits those himself in admin.
- Chrome extension edits go directly into the extension folder in Niral's Downloads (via the linked computer), not a new zip.
- Commit messages end with the session attribution lines; push to `main` (GitHub Actions builds and publishes in ~3 min).
