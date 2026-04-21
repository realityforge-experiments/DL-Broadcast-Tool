# ---------------------------------------------------------
# Anchor Tag — Defensive Stability & Survivability
# Mode-agnostic, uses only universal stats
# ---------------------------------------------------------

from tags.tag_framework import build_tag_output

# ---------------------------------------------------------
# Anchor Summary (caster-friendly)
# ---------------------------------------------------------

def anchor_summary(tier, pct):
    if tier == "S":
        return f"Elite defensive anchor — top {100 - pct:.0f}% in the league for survivability and stability."
    if tier == "A":
        return "High-impact anchor with strong survivability and consistent defensive presence."
    if tier == "B":
        return "Above-average anchor who provides reliable defensive value."
    if tier == "C":
        return "Below-average anchor; inconsistent survivability or defensive presence."
    return "Struggles to provide defensive stability."


# ---------------------------------------------------------
# Survivability Normalization
# ---------------------------------------------------------

def compute_survivability_norm(deaths_per_map, league_avg_deaths):
    """
    Survivability = league_avg / player_deaths
    Clamped to [0.25, 1.50], then normalized to 0–1.
    """
    if deaths_per_map <= 0:
        # Extremely rare, but treat as max survivability
        return 1.0

    raw = league_avg_deaths / deaths_per_map

    # Clamp to avoid extreme values
    raw = max(0.25, min(1.50, raw))

    # Normalize to 0–1
    return (raw - 0.25) / (1.50 - 0.25)


# ---------------------------------------------------------
# Defensive Presence Normalization
# ---------------------------------------------------------

def compute_defensive_presence_norm(damage_per_map, league_avg_damage):
    """
    Defensive presence uses damage as a universal proxy.
    Normalized to league average, clamped to [0, 1.5], then normalized to 0–1.
    """
    if league_avg_damage <= 0:
        return 0.0

    raw = damage_per_map / league_avg_damage

    # Clamp
    raw = max(0.0, min(1.5, raw))

    # Normalize to 0–1
    return raw / 1.5


# ---------------------------------------------------------
# Anchor Raw Score
# ---------------------------------------------------------

def compute_anchor_raw(pdata, league_averages, consistency_norm):
    """
    pdata: player stats dict (career-level)
    league_averages: dict with league-wide averages
    consistency_norm: 0–1 normalized consistency score
    """

    c = pdata["career"]

    deaths = c["deaths"]
    damage = c["damage"]
    maps = max(1, c["maps"])

    deaths_per_map = deaths / maps
    damage_per_map = damage / maps

    league_avg_deaths = league_averages.get("deaths_per_map", 1)
    league_avg_damage = league_averages.get("damage", 1)

    survivability = compute_survivability_norm(deaths_per_map, league_avg_deaths)
    defensive_presence = compute_defensive_presence_norm(damage_per_map, league_avg_damage)

    # Weighted anchor score
    raw = (
        survivability * 0.45 +
        defensive_presence * 0.30 +
        consistency_norm * 0.25
    )

    return max(0.0, min(1.0, raw))


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def compute_anchor_for_career_player(pdata, league_averages, anchor_distribution, consistency_norm):
    """
    pdata: player stats
    league_averages: league-wide averages
    anchor_distribution: distribution of raw anchor scores for percentile mapping
    consistency_norm: 0–1 normalized consistency score (from consistency tag)
    """
    raw = compute_anchor_raw(pdata, league_averages, consistency_norm)
    return build_tag_output(raw, anchor_distribution, anchor_summary)