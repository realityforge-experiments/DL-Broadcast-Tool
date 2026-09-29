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

    


def build_career_database(output_path, current_season=None):
    
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

        # Infer "first season" from earliest CycleID — this is on a
        # completely different numbering scale than the caster's own
        # "current_season" (e.g. 11), it's the raw API cycle counter, so
        # it's kept ONLY as an informational/display value below. It is
        # NOT used to stamp the identity registry's season tracking
        # (that's what caused last_season to be unusable for recency
        # checks elsewhere in the app — mixing two incompatible scales).
        first_cycle = min(m.get("CycleID", 0) for m in matches) or 0

        # Resolve canonical identity. If the caller passed the caster's
        # current_season (the GUI always does), use that consistently
        # with on_sync_stats so last_season stays on one comparable
        # scale across the whole app. Only fall back to the raw CycleID
        # scale if this is being run standalone with no season context.
        season_for_resolve = current_season if current_season is not None else first_cycle
        canonical_id = pir.resolve(raw_uuid, season=season_for_resolve)
        pir.add_name(canonical_id, name)
        pid = canonical_id

        career_raw = defaultdict(float)
        teams_seen = [] 

        # LOOKUP CLEAN NAMES FROM REGISTRY
        reg_entry = pir.data["canonical"].get(pid, {})
        reg_teams = reg_entry.get("team_history", [])

        # Prefer the identity registry's LATEST name over the static
        # SQL-sourced one. Without this, rebuilding would silently
        # revert any rename applied via Manage Roster back to whatever
        # name was in the local database at the time it was imported —
        # a rebuild should never undo a caster's rename.
        display_name = reg_entry["names"][-1] if reg_entry.get("names") else name

        for m in matches:
            # 1. Handle Team Names
            t_raw = str(m.get("TeamUUID") or m.get("team") or "")
            
            # Use registry name if available, otherwise raw
            clean_team = reg_teams[-1] if reg_teams else t_raw
            
            if clean_team and (not teams_seen or teams_seen[-1] != clean_team):
                # Filter out raw UUIDs (e.g. "e960a65e...")
                if not (len(clean_team) > 20 and "-" in clean_team):
                    teams_seen.append(clean_team)

            # 2. Aggregate Stats (Including Score)
            career_raw["kills"] += m.get("Kills", 0)
            career_raw["deaths"] += m.get("Deaths", 0)
            career_raw["damage"] += m.get("Damage", 0)
            career_raw["score"] += m.get("Score", 0)
            career_raw["shots"] += m.get("Shots", 0)
            career_raw["shots_hit"] += m.get("ShotsHit", 0)
            career_raw["headshots"] += m.get("Headshots", 0)
            career_raw["PAY_PushTime"] += m.get("PAY_PushTime", 0)
            career_raw["DOM_Captures"] += m.get("DOM_Captures", 0) 
            career_raw["DOM_Counters"] += m.get("DOM_Counters", 0)
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
            "name": display_name,
            "first_season": pir.get_first_season(canonical_id), 
            "team_history": teams_seen, 
            "career": {
                "kills": career_raw["kills"],
                "deaths": career_raw["deaths"],
                "score": career_raw["score"],
                "KD": KD,
                "accuracy": accuracy,
                "push_time": career_raw["PAY_PushTime"],
                "DOM_Captures": int(career_raw["DOM_Captures"]),
                "DOM_Counters": int(career_raw["DOM_Counters"]),
                "maps": int(career_raw["maps"]),
                "damage": career_raw["damage"],
                "shots": career_raw["shots"],
                "shots_hit": career_raw["shots_hit"],
                "headshots": career_raw["headshots"],
            },
            "DOM_Captures": int(career_raw["DOM_Captures"]),
            "DOM_Counters": int(career_raw["DOM_Counters"]),
            "derived": derived,
            "matches": matches,
        }

    # ---------------------------------------------------------
    # 3. PRE-COMPUTE RAW VALUES FOR DISTRIBUTIONS
    # ---------------------------------------------------------
    all_players = list(final_db["players"].values())

    for pdata in all_players:
        # A. Clutch Raw
        pdata["clutch_raw"] = compute_clutch_raw(pdata)
        
        # B. Consistency Raw (Calibration for Top Players)
        matches = pdata.get("matches", [])
        per_match_scores = []
        for m in matches:
            # Calculate a "Performance Score" for every single match played
            s_kills = m.get("Kills", 0)
            s_deaths = max(1, m.get("Deaths", 0))
            s_dmg = m.get("Damage", 0)
            
            # Simple match power formula
            match_perf = (s_kills / 25) * 0.4 + (s_dmg / 8000) * 0.4 + ((s_kills / s_deaths) / 4) * 0.2
            per_match_scores.append(match_perf)

        if len(per_match_scores) > 1:
            mean = sum(per_match_scores) / len(per_match_scores)
            # Variance calculation
            var = sum((x - mean) ** 2 for x in per_match_scores) / len(per_match_scores)
            # Use Standard Deviation (sqrt of variance) to avoid punishing high-scorers
            pdata["consistency_raw"] = 1 / (1 + (var ** 0.5))
        else:
            # Default for players with only 1 match (can't measure consistency yet)
            pdata["consistency_raw"] = 0.5

    # ---------------------------------------------------------
    # 4. Compute League Metrics (Distributions now populated)
    # ---------------------------------------------------------
    league_averages, distributions = compute_league_metrics(all_players)
    clutch_averages, clutch_distribution = compute_league_clutch_metrics(all_players)
    league_averages.update(clutch_averages)
    final_db["league_averages"] = league_averages

    # ---------------------------------------------------------
    # 5. Finalize Tag Calculation (Percentiles & Tiers)
    # ---------------------------------------------------------
    # ---------------------------------------------------------
    # Breaker distribution — computed ONCE, outside the per-player
    # loop below. This used to be recomputed from scratch for every
    # single player inside the loop (twice, in two redundant blocks),
    # making this O(n²) instead of O(n) for no reason — harmless to
    # correctness but very wasteful for a large league.
    # ---------------------------------------------------------
    breaker_dist = sorted(
        (p["career"]["damage"] / max(1, p["career"]["maps"])) * 0.6
        + (p["career"]["kills"] / max(1, p["career"]["maps"])) * 0.4
        for p in all_players
    )

    for pid, pdata in final_db["players"].items():
        career = pdata["career"]

        # --- Standard Tags ---
        pdata["slayer"] = compute_slayer_for_career_player(pdata, league_averages, distributions["slayer"])
        pdata["sharpshooter"] = compute_sharpshooter_for_career_player(career, league_averages, distributions["sharpshooter"])
        pdata["objective_payload"] = compute_payload_tag(pdata, league_averages, distributions["payload"])
        pdata["objective_domination"] = compute_dom_objective_for_career_player(pdata, league_averages, distributions["domination"])

        # --- Consistency Tag (Fixed logic) ---
        raw_cons = pdata.get("consistency_raw", 0.5)
        cons_pct = percentile_rank(raw_cons, distributions.get("consistency", []))
        cons_tier = tier_from_percentile(cons_pct)
        pdata["consistency"] = {
            "raw": raw_cons,
            "pct": cons_pct,
            "tier": cons_tier,
            "summary": f"{cons_tier} Tier Stability ({cons_pct:.1f} percentile)"
        }

        # --- Advanced Tags ---
        pdata["anchor"] = compute_anchor_for_career_player(pdata, league_averages, distributions["anchor"], raw_cons)

        # FIX: Ensure we use the pre-calculated clutch_distribution
        pdata["clutch"] = compute_clutch(pdata, league_averages, clutch_distribution)

        # --- Breaker Tag ---
        dmg_map = career["damage"] / max(1, career["maps"])
        kills_map = career["kills"] / max(1, career["maps"])
        raw_breaker = compute_breaker_raw(dmg_map, kills_map)
        break_pct = percentile_rank(raw_breaker, breaker_dist)
        break_tier = tier_from_percentile(break_pct)

        pdata["breaker"] = {
            "raw": raw_breaker,
            "pct": break_pct,
            "tier": break_tier,
            "summary": f"{break_tier} Tier Offensive Disruptor"
        }

    # ---------------------------------------------------------
    # 6. Save and Finish
    # ---------------------------------------------------------
    # Save the full league-wide raw-score distribution for every tag.
    # This lets fallback/estimated players (missing from this database
    # entirely, handled elsewhere via resolve_tag_career_first) be
    # percentile-ranked against the SAME real population career players
    # use, instead of only against each other in a single match — which
    # was producing misleading percentiles (a higher raw score could
    # show a LOWER percentile than a lower raw score from a different
    # player, because they were being measured against two completely
    # different, tiny vs. league-wide, populations).
    final_db["distributions"] = {
        "slayer": distributions.get("slayer", []),
        "sharpshooter": distributions.get("sharpshooter", []),
        "objective_payload": distributions.get("payload", []),
        "objective_domination": distributions.get("domination", []),
        "consistency": distributions.get("consistency", []),
        "anchor": distributions.get("anchor", []),
        "clutch": clutch_distribution,
        "breaker": breaker_dist,
    }

    pir.save()
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_db, f, indent=2)

    return True