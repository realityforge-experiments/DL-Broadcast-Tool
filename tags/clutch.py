import math

def compute_clutch(player_entry, league_averages=None):
    """
    Computes a normalized clutch score (0–1) based on:
    - Pressure Efficiency (40%)
    - Collapse Avoidance (40%)
    - Conversion Rate (20%)
    """

    career = player_entry.get("career", {})
    maps = career.get("maps", 0)

    if maps <= 0:
        return 0.0

    # -----------------------------
    # PRESSURE EFFICIENCY (40%)
    # -----------------------------
    damage = career.get("damage", 0)
    deaths = career.get("deaths", 0)

    pressure_eff = damage / (deaths + 1)

    # Normalize pressure using log scale
    # If league averages exist, use them; otherwise fallback to self-normalization
    if league_averages and "pressure_eff" in league_averages:
        denom = math.log(1 + league_averages["pressure_eff"])
    else:
        denom = math.log(1 + pressure_eff) if pressure_eff > 0 else 1

    pressure_norm = math.log(1 + pressure_eff) / max(1e-6, denom)

    # -----------------------------
    # COLLAPSE AVOIDANCE (40%)
    # -----------------------------
    # Reuse consistency floor logic if available
    consistency = player_entry.get("consistency_components", {})
    floor_score = consistency.get("consistency_norm", 0.0)

    collapse_avoid = floor_score  # already normalized 0–1

    # -----------------------------
    # CONVERSION RATE (20%)
    # -----------------------------
    shots = career.get("shots", 0)
    shots_hit = career.get("shots_hit", 0)
    headshots = career.get("headshots", 0)

    accuracy = shots_hit / max(1, shots)
    headshot_rate = headshots / max(1, shots_hit)

    # Normalize accuracy + headshot rate
    conversion = (accuracy * 0.50) + (headshot_rate * 0.50)

    # -----------------------------
    # FINAL CLUTCH SCORE
    # -----------------------------
    clutch_raw = (
        (pressure_norm * 0.40) +
        (collapse_avoid * 0.40) +
        (conversion * 0.20)
    )

    return max(0.0, min(1.0, clutch_raw))