# Kollect Korner — One Piece TCG Preorder Watcher

Watches Kollect Korner's preorders feed and pings a Discord channel the
moment a **One Piece TCG Booster Box or Booster Pack Display** preorder is
live AND in stock — before you'd ever have a direct product link.

## How it works
- Every 15 minutes, GitHub Actions runs `monitor.py` for free.
- The script reads the store's public Shopify JSON feed (`products.json`),
  filters for "One Piece" + ("booster box" or "booster pack display" /
  "booster display"), and checks each matching product's variants for
  `available: true`.
- It only pings when a matching product is actually purchasable — a
  listing that's up but shows "Sold out" will NOT trigger a notification.
- It tracks each product's availability across runs (in `seen_products.json`,
  committed back to the repo each run), so you get pinged for:
  - a **brand-new** listing that's already in stock, and
  - an **existing** listing that was sold out and just became available
    again (a restock/new allocation drop) — the Discord message will say
    "Back in stock" for these.
- If a product is already in stock and stays in stock across runs, you
  won't get repeat pings for it.
- The very first run just records a baseline (everything currently listed,
  in stock or not) so you don't get flooded with alerts for existing
  preorders — only genuinely new stock events from then on.

## Setup (10 minutes, no coding required)

### 1. Create a Discord webhook
1. In Discord, go to the channel you want alerts in → **Edit Channel** →
   **Integrations** → **Webhooks** → **New Webhook**.
2. Name it (e.g. "Preorder Bot"), then **Copy Webhook URL**. Keep this handy.

### 2. Create a GitHub repo
1. Go to github.com → **New repository** (can be private).
2. Upload these files, preserving the folder structure:
   - `monitor.py`
   - `.github/workflows/monitor.yml`
   - `seen_products.json` (empty placeholder is fine — it'll be filled in on first run)
   - `README.md` (optional, just for your own reference)

### 3. Add the webhook as a secret
1. In your new repo: **Settings** → **Secrets and variables** → **Actions**
   → **New repository secret**.
2. Name: `DISCORD_WEBHOOK_URL`
   Value: (paste the webhook URL from step 1)

### 4. Enable Actions and do a first run
1. Go to the **Actions** tab of your repo → you may need to click
   "I understand my workflows, go ahead and enable them."
2. Click into **"Kollect Korner One Piece Preorder Watch"** → **Run workflow**
   (this triggers the baseline run manually so you don't have to wait 15 min).
3. After it finishes, check that `seen_products.json` was updated with a
   commit — that confirms it's working.

That's it — from here it runs automatically every 15 minutes. When a new
One Piece booster box/display preorder appears, you'll get a Discord ping
within 15 minutes of it going live.

## Adjusting things later
- **Check frequency**: edit the `cron` line in `monitor.yml`
  (`*/15 * * * *` = every 15 min; GitHub's minimum practical interval is
  about 5 min, though it's not always exact under load).
- **Keywords**: edit `KEYWORDS_REQUIRED_ALL` / `KEYWORDS_REQUIRED_ANY` at the
  top of `monitor.py` to watch for other franchises/products too.
- **If the JSON feed ever stops working**: the script already falls back
  from `/collections/preorders/products.json` to `/products.json`. If
  Kollect Korner blocks both, let me know and I'll switch it to parse the
  HTML page instead.
