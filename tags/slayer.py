import math
from tags.tag_framework import build_tag_output

# ---------------------------------------------------------
# Slayer Summary (caster-friendly)
# ---------------------------------------------------------

def slayer_summary(tier, pct):
    if tier == "S":
        return f"Elite eliminator — top {100 - pct:.0f}% in the league for damage and kills."
    if tier == "A":
        return "High-impact slayer with strong duel presence and damage output."
    if tier == "B":
        return "Above-average slayer with reliable elimination pressure."
    if tier == "C":
        return "Below-average slayer; inconsistent duel presence."
    return "Struggles to generate elimination pressure."


# ---------------------------------------------------------
# Slayer Raw Score (existing logic preserved)
# ---------------------------------------------------------

def compute_slayer_raw(pdata, league_averages):
    c = pdata["career"]

    kills = c["kills"]
    deaths = c["deaths"]
    damage = c["damage"]
    maps = max(1, c["maps"])

    kd = kills / deaths if deaths > 0 else kills
    dmg_per_map = damage / maps

    # Normalize against league averages
    kd_norm = kd / max(1e-6, league_averages.get("KD", 1))
    dmg_norm = dmg_per_map / max(1e-6, league_averages.get("damage", 1))

    # Weighted slayer score
    raw = (kd_norm * 0.60) + (dmg_norm * 0.40)
    return max(0.0, min(1.0, raw))


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def compute_slayer_for_career_player(pdata, league_averages, slayer_distribution):
    raw = compute_slayer_raw(pdata, league_averages)
    return build_tag_output(raw, slayer_distribution, slayer_summary)