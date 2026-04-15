import os
import json
from collections import defaultdict
import data.db_access as db_access

from tags.slayer import compute_slayer_for_career_player
from tags.objective_payload import compute_payload_tag
from tags.objective_domination import compute_dom_objective_for_career_player
from tags.sharpshooter import compute_sharpshooter_for_career_player
from tags.consistency import build_consistency_tag
from tags.clutch import compute_clutch, compute_clutch_raw
from tags.support_specialist import build_support_specialist_tag

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
    # NORMALIZE CAREER STAT KEYS BEFORE LEAGUE METRICS
    # ---------------------------------------------------------
    for pid, pdata in final_db["players"].items():
        career = pdata.get("career", {})

        career["push_time"] = (
            career.get("push_time")
            or career.get("PAY_PushTime")
            or pdata.get("PAY_PushTime")
            or 0
        )

        career["captures"] = (
            career.get("captures")
            or career.get("DOM_Captures")
            or pdata.get("DOM_Captures")
            or 0
        )

        career["counters"] = (
            career.get("counters")
            or career.get("DOM_Counters")
            or pdata.get("DOM_Counters")
            or 0
        )

        career["damage"] = (
            career.get("damage")
            or career.get("Damage")
            or pdata.get("Damage")
            or 0
        )

        career["kills"] = (
            career.get("kills")
            or career.get("Kills")
            or pdata.get("Kills")
            or 0
        )

        career["deaths"] = (
            career.get("deaths")
            or career.get("Deaths")
            or pdata.get("Deaths")
            or 0
        )

        career["maps"] = (
            career.get("maps")
            or pdata.get("maps")
            or pdata.get("career", {}).get("maps")
            or 1
        )

        pdata["career"] = career    
            
            
            

    # ---------------------------------------------------------
    # 4. Compute league metrics for ALL TAGS
    # ---------------------------------------------------------
    league_averages, distributions = compute_league_metrics(all_players)
    clutch_averages, clutch_distribution = compute_league_clutch_metrics(all_players)

    # Merge clutch averages into league averages
    league_averages.update(clutch_averages)

    final_db["league_averages"] = league_averages
    
    
    from tags.support_specialist import compute_support_specialist  # at top of file if not already

    # ---------------------------------------------------------
    # 4.5 Build Support Specialist distribution
    # ---------------------------------------------------------
    support_distribution = []
    for pid, pdata in final_db["players"].items():
        raw_support = compute_support_specialist(pdata, league_averages)
        support_distribution.append(raw_support)

        # Write back normalized career block
        pdata["career"] = career

    
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
        pdata["objective_domination"] = compute_dom_objective_for_career_player(
            pdata,
            league_averages,
            distributions["domination"]
        )

        # Consistency (legacy adapter)
        consistency_result = build_consistency_tag(
            floor_current=pdata.get("floor_current"),
            floor_career=pdata.get("floor_career"),
            floor_league=league_averages.get("consistency_floor", 0.0),
            stability_current=pdata.get("stability_current"),
            stability_career=pdata.get("stability_career"),
            stability_league=league_averages.get("consistency_stability", 0.0),
            average_current=pdata.get("average_current"),
            average_career=pdata.get("average_career"),
            average_league=league_averages.get("consistency_average", 0.0),
            matches_played_current=pdata["career"].get("maps", 0),
            percentile=None
        )
        pdata["consistency"] = {
            "raw": consistency_result.normalized_score,
            "summary": consistency_result.summary_short
        }

        # Clutch
        pdata["clutch"] = compute_clutch(
            pdata,
            league_averages,
            clutch_distribution
        )

        # Support Specialist
        pdata["support_specialist"] = build_support_specialist_tag(
            pdata,
            league_averages,
            support_distribution
        )

        # ---------------------------------------------------------
        # Consistency (Hybrid Career Tag - New System)
        # ---------------------------------------------------------

        matches = pdata["matches"]
        maps_played = pdata["career"].get("maps", 0)

        # ---------------------------------------------------------
        # Extract per-match performance components
        # ---------------------------------------------------------
        # NOTE:
        # If you later add per-match slayer/objective/accuracy scores,
        # this block will automatically support them.
        # For now, we compute a simple per-match performance score
        # using the same formula as the legacy system.
        # ---------------------------------------------------------

        per_match_scores = []
        for m in matches:
            # Slayer-like component
            dmg = m.get("Damage", 0)
            kills = m.get("Kills", 0)
            deaths = m.get("Deaths", 0)
            kd = kills / deaths if deaths > 0 else kills

            slayer_component = (
                (dmg / 10000) * 0.40 +
                (kills / 30) * 0.40 +
                (kd / 5) * 0.20
            )

            # Objective-like component
            push = m.get("PAY_PushTime", 0)
            caps = m.get("DOM_Captures", 0)
            counters = m.get("DOM_Counters", 0)

            objective_component = (
                (push / 300) * 0.40 +
                (caps / 20) * 0.30 +
                (counters / 20) * 0.30
            )

            # Accuracy-like component
            shots = m.get("Shots", 0)
            shots_hit = m.get("ShotsHit", 0)
            accuracy = (shots_hit / shots) if shots > 0 else 0.0

            accuracy_component = accuracy * 0.20

            # Final per-match performance score
            perf = slayer_component + objective_component + accuracy_component
            per_match_scores.append(perf)

        # ---------------------------------------------------------
        # Compute floor, stability, average
        # ---------------------------------------------------------
        if per_match_scores:
            floor_value = min(per_match_scores)
            avg_value = sum(per_match_scores) / len(per_match_scores)

            # Variance adjusted for match count
            mean = avg_value
            variance = sum((x - mean) ** 2 for x in per_match_scores) / len(per_match_scores)
            adjusted_variance = variance * (1 + 1 / max(1, len(per_match_scores)))
            stability_value = 1 / (1 + adjusted_variance)
        else:
            floor_value = 0.0
            avg_value = 0.0
            stability_value = 0.0

        # ---------------------------------------------------------
        # Build hybrid consistency tag
        # ---------------------------------------------------------
        consistency_result = build_consistency_tag(
            floor_current=floor_value,
            floor_career=floor_value,      # career = all matches
            floor_league=league_averages.get("consistency_floor", 0.0),

            stability_current=stability_value,
            stability_career=stability_value,
            stability_league=league_averages.get("consistency_stability", 0.0),

            average_current=avg_value,
            average_career=avg_value,
            average_league=league_averages.get("consistency_average", 0.0),

            matches_played_current=maps_played,
            percentile=None
        )

        # ---------------------------------------------------------
        # Store in DB (GUI + Rankings + Spotlight compatible)
        # ---------------------------------------------------------
        pdata["consistency"] = {
            "raw": consistency_result.normalized_score,
            "pct": consistency_result.percentile,
            "tier": consistency_result.tier,
            "summary": consistency_result.summary_short,
            "components": {
                "floor": consistency_result.components.floor,
                "stability": consistency_result.components.stability,
                "average": consistency_result.components.average_performance,
            },
            "extras": consistency_result.extras,
        }

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