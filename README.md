# LTO Tracker (auto-updating)

Every 6 hours a GitHub Action collects chain posts, asks Claude to pull out limited-time items and their end dates,
and commits `lto.json`. `index.html` reads that file, so GitHub Pages serves a site that updates itself.

## Setup (about 10 minutes)
1. Create a GitHub repo and push this folder to its root (keep `.github/workflows/update.yml`).
2. Repo > Settings > Secrets and variables > Actions, add:
   - `ANTHROPIC_API_KEY` (required)
   - `X_BEARER_TOKEN` (for X posts; see access note below)
   - `VENDOR_TOKEN` (optional, for Instagram/TikTok/Facebook via a data provider)
3. Settings > Pages > deploy from the main branch, root folder.
4. Actions tab > "Update LTO data" > Run workflow, to test the first run.

Local test: `pip install -r requirements.txt`, set the env vars, run `python collector.py --dry-run`.

## Platform coverage
- **X:** official API, needs a bearer token. Read access on X's free tier is very limited; expect to need a paid tier for ~18 chains.
- **Instagram, TikTok, Facebook:** these have no public API for reading other brands' posts, and scraping them directly breaks their terms. Use a data provider (social-listening or scraping vendor) that returns JSON, and point a `type: json` source at it in `config.yaml`.
- **News/aggregator RSS:** included (Brand Eating) as a free backstop that often states end dates.

## How accuracy is protected
- An end date is only recorded if the post states one explicitly. "While supplies last" stays "not announced".
- Dates before the post date or more than ~13 months out are discarded; low-confidence extractions are dropped.
- A newer explicit end date replaces an older one. Expired items are removed; undated items go stale after 60 days.
- Post text is treated as untrusted data, and the page only links http(s) URLs.
- Limits: item names are fuzzy-matched, so a rare duplicate can slip through. Spot-check `lto.json` now and then, and verify the X handles in `config.yaml`.
