import math

from tags.slayer import compute_slayer_raw
from tags.sharpshooter import compute_sharpshooter_raw
from tags.objective_payload import compute_payload_raw
from tags.objective_domination import compute_dom_raw


# ---------------------------------------------------------
# LEAGUE METRICS FOR ALL TAGS (EXCEPT CLUTCH)
# ---------------------------------------------------------

def compute_league_metrics(all_players):
    """
    Computes league-wide averages and raw-score distributions for:
        - slayer
        - sharpshooter
        - payload
        - consistency
        - domination
    """

    # -----------------------------------------
    # League averages accumulators
    # -----------------------------------------
    acc = {
        "KD": [],
        "accuracy": [],
        "damage": [],
        "push_time": [],
        "headshot_rate": [],
        "pressure_eff": [],
        "deaths": [],
        "dom_actions": [],
    }

    # -----------------------------------------
    # Raw distributions for percentile ranking
    # -----------------------------------------
    dist = {
        "slayer": [],
        "sharpshooter": [],
        "payload": [],
        "consistency": [],
        "domination": [],
        "anchor": [],
        "breaker": [],
    }

    # -----------------------------------------
    # Build league averages (PER-MAP NORMALIZED)
    # -----------------------------------------
    for p in all_players:
        c = p.get("career", {})
        maps = c.get("maps", 0)
        if maps <= 0:
            continue

        # Per-map normalization
        kills = c.get("kills", 0) / maps
        deaths = c.get("deaths", 0) / maps
        damage = c.get("damage", 0) / maps
        push = c.get("push_time", 0) / maps
        captures = c.get("captures", c.get("DOM_Captures", 0)) / maps
        counters = c.get("counters", c.get("DOM_Counters", 0)) / maps

        shots = c.get("shots", 0)
        shots_hit = c.get("shots_hit", 0)
        headshots = c.get("headshots", 0)

        KD = kills / deaths if deaths > 0 else kills
        accuracy = shots_hit / shots if shots > 0 else 0
        headshot_rate = headshots / shots_hit if shots_hit > 0 else 0
        pressure_eff = damage / (deaths + 1)

        acc["KD"].append(KD)
        acc["accuracy"].append(accuracy)
        acc["damage"].append(damage)
        acc["push_time"].append(push)
        acc["headshot_rate"].append(headshot_rate)
        acc["pressure_eff"].append(pressure_eff)
        acc["deaths"].append(deaths)
        acc["dom_actions"].append(captures + counters)

    # -----------------------------------------
    # Compute league averages
    # -----------------------------------------
    league_averages = {
        key: (sum(values) / max(1, len(values)))
        for key, values in acc.items()
    }
    
    # Alias for clarity: deaths is already per-map
    league_averages["deaths_per_map"] = league_averages.get("deaths", 0.0)

    # Minimum smoothing to avoid divide-by-zero explosions
    league_averages["accuracy"] = max(league_averages["accuracy"], 0.05)
    league_averages["headshot_rate"] = max(league_averages["headshot_rate"], 0.03)

    # -----------------------------------------
    # Build raw distributions
    # -----------------------------------------
    for p in all_players:
        c = p.get("career", {})
        matches = p.get("matches", [])

        # Slayer
        dist["slayer"].append(compute_slayer_raw(p, league_averages))

        # Sharpshooter
        dist["sharpshooter"].append(compute_sharpshooter_raw(c, league_averages))

        # Payload
        dist["payload"].append(compute_payload_raw(p))

        # Domination
        dist["domination"].append(compute_dom_raw(p))
        
        from tags.anchor import compute_anchor_raw

        # Consistency raw score for distribution building
        # (You already compute consistency later, but for distributions we only need the raw normalized score)
        consistency_norm = p.get("consistency", {}).get("raw", 0.5)

        dist["anchor"].append(
            compute_anchor_raw(p, league_averages, consistency_norm)
        )
        

    # -----------------------------------------
    # Sort distributions
    # -----------------------------------------
    distributions = {
        key: sorted(values)
        for key, values in dist.items()
    }

    return league_averages, distributions


# ---------------------------------------------------------
# CLUTCH METRICS
# ---------------------------------------------------------

def compute_league_clutch_metrics(all_players):
    """
    Computes league-wide averages and raw-score distribution for Clutch.
    """

    clutch_raw_values = []
    pressure_values = []

    for p in all_players:
        clutch_data = p.get("clutch", {})
        raw = p.get("clutch_raw", 0)

        if raw is not None:
            clutch_raw_values.append(raw)

        c = p.get("career", {})
        dmg = c.get("damage", 0)
        deaths = c.get("deaths", 0)
        pressure_eff = dmg / (deaths + 1)
        pressure_values.append(pressure_eff)

    league_averages = {
        "pressure_eff": sum(pressure_values) / max(1, len(pressure_values)),
    }

    clutch_distribution = sorted(clutch_raw_values)

    return league_averages, clutch_distribution


__all__ = [
    "compute_league_metrics",
    "compute_league_clutch_metrics",
]