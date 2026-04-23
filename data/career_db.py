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
from tags.anchor import compute_anchor_for_career_player
from tags.breaker import compute_breaker_raw

from data.league_metrics import compute_league_metrics, compute_league_clutch_metrics
from data.tag_framework import percentile_rank, tier_from_percentile

    


def build_career_database(output_path):
    
    #print("USING DB:", db_access.DB_PATH)


    # ---------------------------------------------------------
    # 1. Load all players from the local SQLite DB
    # ---------------------------------------------------------
    player_rows = db_access.query("""
        SELECT DISTINCT s.PlayerUUID, p.PlayerGameName
        FROM stats s
        LEFT JOIN players p ON p.PlayerUUID = s.PlayerUUID;
    """)

    # ---------------------------------------------------------
    # Load Player Identity Registry (PIR)
    # ---------------------------------------------------------
    from analysis.player_identity_registry import PlayerIdentityRegistry
    pir = PlayerIdentityRegistry()


    if not player_rows:
        print("No players found in local DB.")
        return False

    final_db = {"players": {}, "league_averages": {}}

    # ---------------------------------------------------------
    # 2. Build per-player career stats from local DB
    # ---------------------------------------------------------
    for row in player_rows:
        raw_uuid = str(row["PlayerUUID"])
        name = row["PlayerGameName"] or "Unknown"

        # Get this player's full match history
        matches = db_access.get_player_match_history(raw_uuid)
        if not matches:
            continue

        # Infer "season" from earliest CycleID (or whatever you treat as season)
        first_cycle = min(m.get("CycleID", 0) for m in matches) or 0

        # Resolve canonical identity AND stamp first_season
        canonical_id = pir.resolve(raw_uuid, season=first_cycle)
        pir.add_name(canonical_id, name)

        # Use CANONICAL ID as the key in the career DB
        pid = canonical_id
            
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
    
        
        
    # ---------------------------------------------------------
    # 4.6 Build Breaker distribution
    # ---------------------------------------------------------


    breaker_distribution = []
    for pid, pdata in final_db["players"].items():
        career = pdata["career"]
        damage_per_map = career["damage"] / max(1, career["maps"])
        kills_per_map = career["kills"] / max(1, career["maps"])

        raw_breaker = compute_breaker_raw(damage_per_map, kills_per_map)
        breaker_distribution.append(raw_breaker)    

    
    # ---------------------------------------------------------
    # 5. Compute all tags using distributions
    # ---------------------------------------------------------
    for pid, pdata in final_db["players"].items():

        # -----------------------------------------------------
        # Slayer
        # -----------------------------------------------------
        pdata["slayer"] = compute_slayer_for_career_player(
            pdata,
            league_averages,
            distributions["slayer"]
        )

        # -----------------------------------------------------
        # Sharpshooter
        # -----------------------------------------------------
        pdata["sharpshooter"] = compute_sharpshooter_for_career_player(
            pdata["career"],
            league_averages,
            distributions["sharpshooter"]
        )

        # -----------------------------------------------------
        # Payload Objective Specialist
        # -----------------------------------------------------
        pdata["objective_payload"] = compute_payload_tag(
            pdata,
            league_averages,
            distributions["payload"]
        )

        # -----------------------------------------------------
        # Domination Objective Specialist
        # -----------------------------------------------------
        pdata["objective_domination"] = compute_dom_objective_for_career_player(
            pdata,
            league_averages,
            distributions["domination"]
        )

        # ---------------------------------------------------------
        # Consistency (Hybrid Career Tag - New System)
        # ---------------------------------------------------------
        matches = pdata["matches"]
        maps_played = pdata["career"].get("maps", 0)

        per_match_scores = []
        for m in matches:
            dmg = m.get("Damage", 0)
            kills = m.get("Kills", 0)
            deaths = m.get("Deaths", 0)
            kd = kills / deaths if deaths > 0 else kills

            slayer_component = (
                (dmg / 10000) * 0.40 +
                (kills / 30) * 0.40 +
                (kd / 5) * 0.20
            )

            push = m.get("PAY_PushTime", 0)
            caps = m.get("DOM_Captures", 0)
            counters = m.get("DOM_Counters", 0)

            objective_component = (
                (push / 300) * 0.40 +
                (caps / 20) * 0.30 +
                (counters / 20) * 0.30
            )

            shots = m.get("Shots", 0)
            shots_hit = m.get("ShotsHit", 0)
            accuracy = (shots_hit / shots) if shots > 0 else 0.0
            accuracy_component = accuracy * 0.20

            perf = slayer_component + objective_component + accuracy_component
            per_match_scores.append(perf)

        if per_match_scores:
            floor_value = min(per_match_scores)
            avg_value = sum(per_match_scores) / len(per_match_scores)

            mean = avg_value
            variance = sum((x - mean) ** 2 for x in per_match_scores) / len(per_match_scores)
            adjusted_variance = variance * (1 + 1 / max(1, len(per_match_scores)))
            stability_value = 1 / (1 + adjusted_variance)
        else:
            floor_value = 0.0
            avg_value = 0.0
            stability_value = 0.0

        consistency_result = build_consistency_tag(
            floor_current=floor_value,
            floor_career=floor_value,
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

        pdata["consistency"] = {
            "raw": consistency_result.normalized_score,
            "pct": None,
            "tier": consistency_result.tier,
            "summary": consistency_result.summary_short,
            "components": {
                "floor": consistency_result.components.floor,
                "stability": consistency_result.components.stability,
                "average": consistency_result.components.average_performance,
            },
            "extras": consistency_result.extras,
        }
        
        # ---------------------------------------------------------
        # Career Consistency Percentile + Tier (NEW)
        # ---------------------------------------------------------
        raw_cons = pdata["consistency"]["raw"]
        cons_dist = distributions.get("consistency", [])

        pct = percentile_rank(raw_cons, cons_dist)
        tier = tier_from_percentile(pct)

        pdata["consistency"]["pct"] = pct
        pdata["consistency"]["tier"] = tier
        pdata["consistency"]["summary"] = (
            f"{tier} Tier Consistency ({pct:.1f} percentile)"
        )

        # ---------------------------------------------------------
        # Anchor (requires consistency)
        # ---------------------------------------------------------
        consistency_norm = pdata["consistency"]["raw"]
        pdata["anchor"] = compute_anchor_for_career_player(
            pdata,
            league_averages,
            distributions["anchor"],
            consistency_norm
        )

        # ---------------------------------------------------------
        # Clutch
        # ---------------------------------------------------------
        pdata["clutch"] = compute_clutch(
            pdata,
            league_averages,
            clutch_distribution
        )

        # ---------------------------------------------------------
        # Breaker
        # ---------------------------------------------------------
        career = pdata["career"]
        damage_per_map = career["damage"] / max(1, career["maps"])
        kills_per_map = career["kills"] / max(1, career["maps"])

        raw_breaker = compute_breaker_raw(damage_per_map, kills_per_map)
        pct = percentile_rank(raw_breaker, breaker_distribution)
        tier = tier_from_percentile(pct)

        pdata["breaker"] = {
            "raw": raw_breaker,
            "pct": pct,
            "tier": tier,
            "summary": f"Offensive disruptor ({tier} Tier, {pct:.1f} percentile)"
        }
        
    # Save PIR with first_season stamped for all canonical IDs
    pir.save()    

    # ---------------------------------------------------------
    # 6. Save DB
    # ---------------------------------------------------------
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_db, f, indent=2)

    return True