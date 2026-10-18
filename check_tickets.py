#!/usr/bin/env python3
"""
Ravenna Christmas Market ticket availability monitor.
Checks for tickets and sends macOS + ntfy.sh push notifications.
"""

import json
import os
import subprocess
import sys
import warnings

warnings.filterwarnings("ignore")

import requests
from bs4 import BeautifulSoup

URL = os.environ.get("MONITOR_URL", "https://ursus1404.github.io/ravenna-ticket-monitor/")
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def fetch_tiles() -> list[str]:
    """Fetch the page and return all tile headline texts."""
    resp = requests.get(URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    headlines = soup.select("h2.c-title-on-image-link-text-tile__headline")
    return [h.get_text(strip=True) for h in headlines if h.get_text(strip=True)]


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def notify_macos(title: str, message: str) -> None:
    script = (
        f'display notification "{message}" '
        f'with title "{title}" '
        f'sound name "Glass"'
    )
    subprocess.run(["osascript", "-e", script], check=False)


def notify_ntfy(title: str, message: str) -> None:
    if not NTFY_TOPIC:
        return
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": "urgent",
                "Tags": "ticket,christmas_tree",
                "Click": URL,
            },
            timeout=10,
        )
    except Exception as e:
        print(f"ntfy notification failed: {e}", file=sys.stderr)


def main() -> None:
    try:
        tiles = fetch_tiles()
    except Exception as e:
        print(f"ERROR fetching page: {e}", file=sys.stderr)
        sys.exit(1)

    sold_out = [t for t in tiles if "AUSVERKAUFT" in t.upper()]
    available = [t for t in tiles if "AUSVERKAUFT" not in t.upper()]

    state = load_state()
    prev_sold_out_count = state.get("sold_out_count", len(tiles))

    print(f"Tiles total: {len(tiles)}, sold out: {len(sold_out)}, available: {len(available)}")
    if available:
        print(f"Available: {available}")

    if len(sold_out) < prev_sold_out_count or available:
        # Something became available since last check
        if available:
            msg = "Verfügbar: " + ", ".join(available)
        else:
            msg = f"Weniger ausverkaufte Termine ({len(sold_out)} statt {prev_sold_out_count}) — jetzt schnell sein!"

        print(f"NOTIFICATION: {msg}")
        if sys.platform == "darwin":
            notify_macos("🎄 Ravenna-Tickets verfügbar!", msg)
        notify_ntfy("🎄 Ravenna-Tickets verfügbar!", msg)
    else:
        print("Keine Änderung — alles noch ausverkauft.")

    save_state({
        "sold_out_count": len(sold_out),
        "sold_out": sold_out,
        "available": available,
    })


if __name__ == "__main__":
    main()
