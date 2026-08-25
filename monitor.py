#!/usr/bin/env python3
"""
Kollect Korner One Piece TCG preorder monitor.

Checks the store's Shopify JSON product feed, finds products matching
One Piece + (Booster Box | Booster Pack Display), and posts a Discord
webhook notification only when such a product is IN STOCK — either
because it's newly listed and already available, or because a
previously out-of-stock/sold-out listing just became available
(a restock/allocation drop).

State (last known availability per product) is persisted to a JSON file
so re-runs don't repeat notifications while a product stays in the same
state, and so a later restock still triggers a fresh alert.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

STORE_BASE = "https://www.kollectkorner.com"
# Try the dedicated preorders collection first; fall back to full catalog.
FEED_URLS = [
    f"{STORE_BASE}/collections/preorders/products.json?limit=250",
    f"{STORE_BASE}/products.json?limit=250",
]

STATE_FILE = os.path.join(os.path.dirname(__file__), "seen_products.json")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

KEYWORDS_REQUIRED_ALL = ["one piece"]
KEYWORDS_REQUIRED_ANY = ["booster box", "booster pack display", "booster display"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PreorderWatcher/1.0; +https://github.com/)"
}


def fetch_json(url, retries=3, delay=2):
    req = urllib.request.Request(url, headers=HEADERS)
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
            last_err = e
            time.sleep(delay)
    print(f"Failed to fetch {url}: {last_err}", file=sys.stderr)
    return None


def get_all_products():
    """Try each feed URL (with pagination) until one works."""
    for base_url in FEED_URLS:
        products = []
        page = 1
        while True:
            sep = "&" if "?" in base_url else "?"
            url = f"{base_url}{sep}page={page}"
            data = fetch_json(url)
            if data is None:
                products = []  # this feed failed, try the next one
                break
            batch = data.get("products", [])
            if not batch:
                break
            products.extend(batch)
            if len(batch) < 250:
                break
            page += 1
            if page > 10:  # safety cap
                break
        if products:
            return products
    return []


def matches_keywords(product):
    haystack = " ".join([
        product.get("title", ""),
        product.get("product_type", ""),
        " ".join(product.get("tags", [])) if isinstance(product.get("tags"), list) else str(product.get("tags", "")),
    ]).lower()

    if not all(k in haystack for k in KEYWORDS_REQUIRED_ALL):
        return False
    if not any(k in haystack for k in KEYWORDS_REQUIRED_ANY):
        return False
    return True


def is_in_stock(product):
    """True if at least one purchasable variant is available."""
    variants = product.get("variants", [])
    return any(v.get("available") for v in variants)


def load_state():
    """Returns dict: product_id (str) -> {"available": bool, "title": str}"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            raw = json.load(f)
        # Support migrating from the old "list of ids" format transparently.
        if isinstance(raw, list):
            return {str(pid): {"available": False, "title": ""} for pid in raw}
        return raw
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def product_url(product):
    handle = product.get("handle", "")
    return f"{STORE_BASE}/products/{handle}"


def notify_discord(product, is_restock):
    if not DISCORD_WEBHOOK_URL:
        print("No DISCORD_WEBHOOK_URL set — skipping Discord notification.", file=sys.stderr)
        return

    title = product.get("title", "Unknown product")
    url = product_url(product)
    image = ""
    images = product.get("images", [])
    if images:
        image = images[0].get("src", "")

    price = ""
    variants = product.get("variants", [])
    if variants:
        price = variants[0].get("price", "")

    headline = "Back in stock" if is_restock else "New preorder — in stock now"

    embed = {
        "title": f"🏴‍☠️ {headline}: {title}",
        "url": url,
        "description": f"Price: ${price}" if price else None,
        "color": 0xE3120B,
    }
    if image:
        embed["thumbnail"] = {"url": image}

    payload = {
        "content": "One Piece TCG booster box/display is available for preorder!",
        "embeds": [embed],
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        DISCORD_WEBHOOK_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"Discord notify status: {resp.status}")
    except urllib.error.URLError as e:
        print(f"Failed to notify Discord: {e}", file=sys.stderr)


def main():
    products = get_all_products()
    if not products:
        print("No products fetched from any feed — site may be blocking, or down. Exiting.", file=sys.stderr)
        sys.exit(0)  # don't fail the whole workflow on a transient site issue

    state = load_state()
    is_first_run = len(state) == 0

    matches = [p for p in products if matches_keywords(p)]
    print(f"Checked {len(products)} products, {len(matches)} matched keywords.")

    new_state = dict(state)  # carry forward anything not touched this run
    notified = 0

    for product in matches:
        pid = str(product["id"])
        currently_available = is_in_stock(product)
        prev = state.get(pid)
        prev_available = prev["available"] if prev else None

        if not is_first_run and currently_available and prev_available in (None, False):
            is_restock = prev_available is False  # was tracked before and was OOS
            print(f"IN STOCK: {product.get('title')} -> {product_url(product)} (restock={is_restock})")
            notify_discord(product, is_restock)
            notified += 1

        new_state[pid] = {"available": currently_available, "title": product.get("title", "")}

    if is_first_run:
        print(f"First run — recorded baseline for {len(new_state)} matching products, no notifications sent.")
    else:
        print(f"Sent {notified} notification(s).")

    save_state(new_state)


if __name__ == "__main__":
    main()
