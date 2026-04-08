import os
import json
from collections import defaultdict
import requests

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
SEASON_CACHE_DIR = os.path.join(CACHE_DIR, "seasons")

os.makedirs(SEASON_CACHE_DIR, exist_ok=True)

from tags.slayer import compute_slayer_for_career_player
from tags.objective_payload import compute_payload_objective_for_career_player
from tags.sharpshooter import compute_sharpshooter_for_career_player
from tags.consistency import compute_consistency


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_BASE = "https://dashleague.games/api/v1"


def fetch_json(url):
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def detect_valid_seasons(max_season=50):
    valid = []
    for season in range(0, max_season + 1):
        try:
            url = f"{API_BASE}/stats?season={season}"
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json()
            season_stats = data.get("data", [])
            if isinstance(season_stats, list) and len(season_stats) > 0:
                valid.append(season)
        except Exception:
            continue
    return valid


def fetch_season_stats(season):
    url = f"{API_BASE}/stats?season={season}"
    data = fetch_json(url)
    return data.get("data", [])


def build_career_database(output_path):
    seasons = detect_valid_seasons()
    if not seasons:
        print("No valid seasons found. Aborting career DB build.")
        return False

    players = {}
    league_accumulator = defaultdict(float)
    league_counts = defaultdict(int)

    for season in seasons:
        season_stats = fetch_season_stats(season)
        if not isinstance(season_stats, list):
            continue

        for entry in season_stats:
            if not isinstance(entry, dict):
                continue
                
            # Normalize inconsistent keys
            if "loss" in entry and "losses" not in entry:
                entry["losses"] = entry["loss"]

            if "shots" not in entry:
                entry["shots"] = 0

            if "shots_hit" not in entry:
                entry["shots_hit"] = 0

            if "headshots" not in entry:
                entry["headshots"] = 0

            if "damage" not in entry:
                entry["damage"] = 0

            if "maps" not in entry or entry["maps"] in (None, "Coming Soon!"):
                entry["maps"] = 0

            if "accuracy" not in entry or isinstance(entry["accuracy"], str):
                entry["accuracy"] = 0.0               
                
            pid = entry.get("id")
            if not pid:
                continue

            if pid not in players:
                players[pid] = {
                    "name": entry.get("name", "Unknown"),
                    "team_history": set(),
                    "seasons_played": set(),
                    "per_season": {},
                    "career_raw": defaultdict(float)
                }

            p = players[pid]
            team = entry.get("team") or "No Team"
            p["team_history"].add(team)
            p["seasons_played"].add(season)
            p["per_season"][str(season)] = entry

            for key in [
                "kills",
                "deaths",
                "headshots",
                "accuracy",
                "PAY_PushTime",
                "DOM_captures",
                "DOM_counters",
                "maps",
                "wins",
                "losses",
                "damage",
                "shots",
                "shots_hit",
            ]:
                if key in entry:
                    p["career_raw"][key] += entry.get(key, 0)

            if "KD" in entry:
                league_accumulator["KD"] += entry["KD"]
                league_counts["KD"] += 1
            if "accuracy" in entry:
                league_accumulator["accuracy"] += entry["accuracy"]
                league_counts["accuracy"] += 1
            if "kills" in entry and "maps" in entry and entry["maps"] > 0:
                league_accumulator["kills_per_map"] += entry["kills"] / entry["maps"]
                league_counts["kills_per_map"] += 1
            if "damage" in entry and "maps" in entry and entry["maps"] > 0:
                league_accumulator["damage_per_map"] += entry["damage"] / entry["maps"]
                league_counts["damage_per_map"] += 1
            if "PAY_PushTime" in entry:
                league_accumulator["push_time_per_season"] += entry["PAY_PushTime"]
                league_counts["push_time_per_season"] += 1

    league_averages = {}
    for key in league_accumulator:
        league_averages[key] = league_accumulator[key] / max(1, league_counts[key])

    final_db = {"players": {}, "league_averages": league_averages}

    for pid, pdata in players.items():
        
         # 🔥 Skip players with no valid stats
        if "career_raw" not in pdata or not pdata["career_raw"]:
            continue
            
        # print("DEBUG PLAYER:", pid, pdata["career_raw"])    

        raw = pdata["career_raw"]

        # 🔥 Ensure maps always exists
        if "maps" not in raw:
            raw["maps"] = 0

        maps = raw["maps"] if raw["maps"] > 0 else 1
        seasons_played = len(pdata["seasons_played"])

        kills_per_map = raw["kills"] / maps
        deaths_per_map = raw["deaths"] / maps
        push_time_per_season = raw["PAY_PushTime"] / max(1, seasons_played)

        KD = raw["kills"] / raw["deaths"] if raw["deaths"] > 0 else raw["kills"]
        accuracy = raw["accuracy"] / max(1, seasons_played)

        derived = {
            "kills_per_map": kills_per_map,
            "deaths_per_map": deaths_per_map,
            "push_time_per_season": push_time_per_season,
        }

        final_db["players"][pid] = {
            "name": pdata["name"],
            "team_history": list(pdata["team_history"]),
            "seasons_played": list(pdata["seasons_played"]),
            "per_season": pdata["per_season"],
            "career": {
                "kills": raw["kills"],
                "deaths": raw["deaths"],
                "KD": KD,
                "accuracy": accuracy,
                "push_time": raw["PAY_PushTime"],
                "captures": raw["DOM_captures"],
                "counters": raw["DOM_counters"],
                "maps": raw["maps"],
                "wins": raw["wins"],
                "losses": raw["losses"],
                "damage": raw["damage"],
                "shots": raw.get("shots", 0),
                "shots_hit": raw.get("shots_hit", 0),
                "headshots": raw.get("headshots", 0),
                "damage_dealt": raw.get("damage", 0),
            },
            "derived": derived,
        }
        
        from data.player_history import get_player_match_history

        final_db["players"][pid]["matches"] = get_player_match_history(pid)


                   

     # Compute all tag scores per player
    for pid, pdata in final_db["players"].items():

        # 🔥 Skip players missing a career block
        if "career" not in pdata:
            print("SKIPPING PLAYER WITH NO CAREER:", pid)
            continue

        # Slayer
        slayer_info = compute_slayer_for_career_player(pdata, league_averages)
        pdata["slayer_score_raw"] = slayer_info["score_raw"]
        pdata["slayer_score_display"] = slayer_info["score_display"]
        pdata["slayer_strength"] = slayer_info["strength"]

        # Sharpshooter
        sharp = compute_sharpshooter_for_career_player(pdata["career"])
        pdata["sharpshooter"] = sharp

        # Payload Objective Specialist
        obj_components = compute_payload_objective_for_career_player(pdata, league_averages)
        pdata["objective_payload_components"] = obj_components
        
        
         # --- Consistency Tag ---
        from tags.consistency import compute_consistency

        matches = pdata.get("matches", [])

        consistency_raw, components = compute_consistency(matches)

        pdata["consistency_components"] = {
            **components,
            "consistency_raw": consistency_raw,
            "consistency_norm": components.get("consistency_norm", consistency_raw)
        }
        
        # --- Clutch Tag ---
        from tags.clutch import compute_clutch

        pdata["clutch_components"] = {
            "clutch_norm": compute_clutch(pdata, league_averages)
        }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_db, f, indent=2)

    return True