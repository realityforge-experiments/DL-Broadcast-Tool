import os
import json
import requests

from data.season_cache import fetch_season_match_list, BASE as API_BASE
from data.match_cache import fetch_match_details

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
PLAYER_CACHE_DIR = os.path.join(CACHE_DIR, "players")
SEASON_CACHE_DIR = os.path.join(CACHE_DIR, "seasons")

os.makedirs(PLAYER_CACHE_DIR, exist_ok=True)
os.makedirs(SEASON_CACHE_DIR, exist_ok=True)


def _detect_cached_seasons():
    out = []
    for filename in os.listdir(SEASON_CACHE_DIR):
        if filename.endswith("_matches.json"):
            sid = filename.replace("_matches.json", "")
            if sid.isdigit():
                out.append(sid)
    return out


def _fetch_all_seasons_from_api():
    try:
        resp = requests.get(f"{API_BASE}/seasons", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print("ERROR fetching seasons:", e)
        return []


def get_player_match_history(player_id):
    """Build full match history for a player using cached data."""

    cache_path = os.path.join(PLAYER_CACHE_DIR, f"{player_id}_matches.json")

    # --- Use cached player history if available ---
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("ERROR reading cached player history:", e)

    history = []

    # --- Load cached seasons ---
    seasons = _detect_cached_seasons()

    # --- If no cached seasons exist, fetch them ---
    if not seasons:
        print("No cached seasons found. Fetching from API...")
        season_list = _fetch_all_seasons_from_api()

        for s in season_list:
            sid = s.get("id")
            if sid:
                print(f"Caching season {sid} match list...")
                fetch_season_match_list(sid)

        seasons = _detect_cached_seasons()

    # --- Process each season ---
    for season_id in seasons:
        print(f"Processing season {season_id}...")
        match_list = fetch_season_match_list(season_id)

        for match_entry in match_list:
            match_id = match_entry.get("id")
            if not match_id:
                continue

            match_data = fetch_match_details(match_id)
            if not match_data:
                continue

            mode = match_data.get("mode", "").lower()

            for p in match_data.get("players", []):
                if p.get("id") == player_id:

                    entry = {
                        "kills": p.get("kills", 0),
                        "deaths": p.get("deaths", 0),
                        "accuracy": p.get("accuracy", 0.0),
                        "damage": p.get("damage", 0),
                        "push_time": p.get("PAY_PushTime", 0),
                        "captures": p.get("DOM_captures", 0),
                        "counters": p.get("DOM_counters", 0),
                        "mode": mode
                    }

                    history.append(entry)

    # --- Cache the built history ---
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print("ERROR writing player history:", e)

    return history