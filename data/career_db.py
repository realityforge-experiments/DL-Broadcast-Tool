import os
import json
from collections import defaultdict
import data.db_access as db_access

from tags.slayer import compute_slayer_for_career_player
from tags.objective_payload import compute_payload_objective_for_career_player
from tags.sharpshooter import compute_sharpshooter_for_career_player
from tags.consistency import compute_consistency
from tags.clutch import compute_clutch


def build_career_database(output_path):

    # ---------------------------------------------------------
    # 1. Load all players from the local SQLite DB
    # ---------------------------------------------------------
    player_rows = db_access.query("SELECT PlayerUUID, PlayerGameName FROM players;")

    if not player_rows:
        print("No players found in local DB.")
        return False

    final_db = {"players": {}, "league_averages": {}}

    # ---------------------------------------------------------
    # 2. Build per-player career stats from local DB
    # ---------------------------------------------------------
    for row in player_rows:
        pid = row["PlayerUUID"]
        name = row.get("PlayerGameName", "Unknown")

        # Pull all matches from SQLite
        matches = db_access.get_player_match_history(pid)

        if not matches:
            # Skip players with no match history
            continue

        # Aggregate raw career totals
        career_raw = defaultdict(float)

        for m in matches:
            career_raw["kills"] += m["Kills"]
            career_raw["deaths"] += m["Deaths"]
            career_raw["damage"] += m["Damage"]
            career_raw["shots"] += m["Shots"]
            career_raw["shots_hit"] += m["ShotsHit"]
            career_raw["headshots"] += m["Headshots"]
            career_raw["PAY_PushTime"] += m["PAY_PushTime"]
            career_raw["DOM_captures"] += m["DOM_Captures"]
            career_raw["DOM_counters"] += m["DOM_Counters"]
            career_raw["maps"] += 1  # each match = 1 map for now

        # Derived stats
        maps = max(1, career_raw["maps"])
        KD = career_raw["kills"] / career_raw["deaths"] if career_raw["deaths"] > 0 else career_raw["kills"]
        accuracy = (career_raw["shots_hit"] / career_raw["shots"]) if career_raw["shots"] > 0 else 0.0

        derived = {
            "kills_per_map": career_raw["kills"] / maps,
            "deaths_per_map": career_raw["deaths"] / maps,
            "push_time_per_season": career_raw["PAY_PushTime"],  # no seasons now
        }

        final_db["players"][pid] = {
            "name": name,
            "career": {
                "kills": career_raw["kills"],
                "deaths": career_raw["deaths"],
                "KD": KD,
                "accuracy": accuracy,
                "push_time": career_raw["PAY_PushTime"],
                "captures": career_raw["DOM_captures"],
                "counters": career_raw["DOM_counters"],
                "maps": career_raw["maps"],
                "damage": career_raw["damage"],
                "shots": career_raw["shots"],
                "shots_hit": career_raw["shots_hit"],
                "headshots": career_raw["headshots"],
            },
            "derived": derived,
            "matches": matches,
        }

    # ---------------------------------------------------------
    # 3. Compute league averages (local-only)
    # ---------------------------------------------------------
    league_acc = defaultdict(float)
    league_count = defaultdict(int)

    for pid, pdata in final_db["players"].items():
        c = pdata["career"]

        league_acc["KD"] += c["KD"]
        league_count["KD"] += 1

        league_acc["accuracy"] += c["accuracy"]
        league_count["accuracy"] += 1

        league_acc["kills_per_map"] += pdata["derived"]["kills_per_map"]
        league_count["kills_per_map"] += 1

        league_acc["damage"] += c["damage"]
        league_count["damage"] += 1

    league_averages = {
        key: league_acc[key] / max(1, league_count[key])
        for key in league_acc
    }

    final_db["league_averages"] = league_averages

    # ---------------------------------------------------------
    # 4. Compute all tags
    # ---------------------------------------------------------
    for pid, pdata in final_db["players"].items():

        # Slayer
        slayer_info = compute_slayer_for_career_player(pdata, league_averages)
        pdata["slayer_score_raw"] = slayer_info["score_raw"]
        pdata["slayer_score_display"] = slayer_info["score_display"]
        pdata["slayer_strength"] = slayer_info["strength"]

        # Sharpshooter
        pdata["sharpshooter"] = compute_sharpshooter_for_career_player(pdata["career"])

        # Payload Objective Specialist
        pdata["objective_payload_components"] = compute_payload_objective_for_career_player(
            pdata, league_averages
        )

        # Consistency
        matches = pdata["matches"]
        consistency_raw, components = compute_consistency(matches)
        pdata["consistency_components"] = {
            **components,
            "consistency_raw": consistency_raw,
            "consistency_norm": components.get("consistency_norm", consistency_raw),
        }

        # Clutch
        pdata["clutch_components"] = {
            "clutch_norm": compute_clutch(pdata, league_averages)
        }

    # ---------------------------------------------------------
    # 5. Save DB
    # ---------------------------------------------------------
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_db, f, indent=2)

    return True