import os
import json
import requests

BASE = "https://dashleague.games/api/v1"

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
MATCH_CACHE_DIR = os.path.join(CACHE_DIR, "matches")

os.makedirs(MATCH_CACHE_DIR, exist_ok=True)


def fetch_match_details(match_id):
    """
    Returns full match details for a given match_id.
    Uses cache if available.
    """

    cache_path = os.path.join(MATCH_CACHE_DIR, f"{match_id}.json")

    # --- Use cached file if it exists ---
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass  # fall through to API fetch

    # --- Fetch from API ---
    url = f"{BASE}/match/{match_id}"

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        match_data = resp.json()
    except Exception:
        return {}

    # --- Cache the result ---
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(match_data, f, indent=2)
    except Exception:
        pass  # caching failure shouldn't break functionality

    return match_data