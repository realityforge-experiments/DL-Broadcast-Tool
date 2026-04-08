import os
import json
import requests

BASE = "https://dashleague.games/api/v1"

# Cache directories
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
SEASON_CACHE_DIR = os.path.join(CACHE_DIR, "seasons")

# Ensure folders exist
os.makedirs(SEASON_CACHE_DIR, exist_ok=True)


def fetch_season_match_list(season_id):
    """
    Returns the list of matches for a season.
    Uses cache if available.
    """

    cache_path = os.path.join(SEASON_CACHE_DIR, f"{season_id}_matches.json")

    # --- Use cached file if it exists ---
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass  # fall through to API fetch

    # --- Fetch from API ---
    url = f"{BASE}/seasons/{season_id}/matches"

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        matches = resp.json()
    except Exception:
        return []

    # --- Cache the result ---
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(matches, f, indent=2)
    except Exception:
        pass  # caching failure shouldn't break functionality

    return matches