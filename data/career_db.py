import os
import json
from collections import defaultdict
import data.db_access as db_access

from tags.slayer import compute_slayer_for_career_player
from tags.objective_payload import compute_payload_tag
from tags.objective_domination import compute_dom_objective_for_career_player
from tags.sharpshooter import compute_sharpshooter_for_career_player
from tags.consistency import compute_consistency, compute_consistency_tag
from tags.clutch import compute_clutch, compute_clutch_raw

from data.league_metrics import compute_league_metrics, compute_league_clutch_metrics


def build_career_database(output_path):
    
    print("USING DB:", db_access.DB_PATH)


    # ---------------------------------------------------------
    # 1. Load all players from the local SQLite DB
    # ---------------------------------------------------------
    player_rows = db_access.query("""
        SELECT DISTINCT s.PlayerUUID, p.PlayerGameName
        FROM stats s
        LEFT JOIN players p ON p.PlayerUUID = s.PlayerUUID;
    """)

    if not player_rows:
        print("No players found in local DB.")
        return False

    final_db = {"players": {}, "league_averages": {}}

    # ---------------------------------------------------------
    # 2. Build per-player career stats from local DB
    # ---------------------------------------------------------
    for row in player_rows:
        pid = row["PlayerUUID"]
        name = row["PlayerGameName"] or "Unknown"

        matches = db_access.get_player_match_history(pid)
        if not matches:
            continue
            
        #print("DEBUG MATCH ROW FOR", pid, ":", matches[0])
        #break


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
            career_raw["maps"] += 1

        maps = max(1, career_raw["maps"])
        KD = career_raw["kills"] / career_raw["deaths"] if career_raw["deaths"] > 0 else career_raw["kills"]
        accuracy = (career_raw["shots_hit"] / career_raw["shots"]) if career_raw["shots"] > 0 else 0.0

        derived = {
            "kills_per_map": career_raw["kills"] / maps,
            "deaths_per_map": career_raw["deaths"] / maps,
            "push_time_per_season": career_raw["PAY_PushTime"],
        }

        final_db["players"][pid] = {
            "name": name,
            "career": {
                "kills": career_raw["kills"],
                "deaths": career_raw["deaths"],
                "KD": KD,
                "accuracy": accuracy,
                "push_time": career_raw["PAY_PushTime"],
                "DOM_Captures": int(career_raw["DOM_captures"]),
                "DOM_Counters": int(career_raw["DOM_counters"]),
                "maps": career_raw["maps"],
                "damage": career_raw["damage"],
                "shots": career_raw["shots"],
                "shots_hit": career_raw["shots_hit"],
                "headshots": career_raw["headshots"],
            },
            "DOM_Captures": int(career_raw["DOM_captures"]),   # 👈 add this
            "DOM_Counters": int(career_raw["DOM_counters"]),   # 👈 and this
            "derived": derived,
            "matches": matches,
        }

    # ---------------------------------------------------------
    # 3. PRECOMPUTE RAW CLUTCH VALUES (required for distribution)
    # ---------------------------------------------------------
    all_players = list(final_db["players"].values())

    for pdata in all_players:
        pdata["clutch_raw"] = compute_clutch_raw(pdata)

    # ---------------------------------------------------------
    # 4. Compute league metrics for ALL TAGS
    # ---------------------------------------------------------
    league_averages, distributions = compute_league_metrics(all_players)
    clutch_averages, clutch_distribution = compute_league_clutch_metrics(all_players)

    # Merge clutch averages into league averages
    league_averages.update(clutch_averages)

    final_db["league_averages"] = league_averages

    # ---------------------------------------------------------
    # 5. Compute all tags using distributions
    # ---------------------------------------------------------
    for pid, pdata in final_db["players"].items():

        # Slayer
        pdata["slayer"] = compute_slayer_for_career_player(
            pdata,
            league_averages,
            distributions["slayer"]
        )

        # Sharpshooter
        pdata["sharpshooter"] = compute_sharpshooter_for_career_player(
            pdata["career"],
            league_averages,
            distributions["sharpshooter"]
        )

        # Payload Objective Specialist
        pdata["objective_payload"] = compute_payload_tag(
            pdata,
            league_averages,
            distributions["payload"]
        )

        # Domination Objective Specialist
        pdata["objective_domination_components"] = compute_dom_objective_for_career_player(
            pdata,
            league_averages,
            distributions["domination"]
        )

        # Consistency
        matches = pdata["matches"]
        consistency_raw, components = compute_consistency(matches)
        pdata["consistency"] = compute_consistency_tag(
            components,
            distributions["consistency"]
        )

        # Clutch (FINAL TAG)
        pdata["clutch"] = compute_clutch(
            pdata,
            league_averages,
            clutch_distribution
        )

    # ---------------------------------------------------------
    # 6. Save DB
    # ---------------------------------------------------------
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_db, f, indent=2)

    return True