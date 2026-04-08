def compute_slayer_for_career_player(p, league_averages):
    career = p["career"]
    maps = career.get("maps", 0) or 0
    kills = career.get("kills", 0) or 0
    deaths = career.get("deaths", 0) or 0
    damage = career.get("damage", 0) or 0

    kd = kills / deaths if deaths > 0 else kills
    dmg_per_map = damage / maps if maps > 0 else 0
    kpm = kills / maps if maps > 0 else 0

    league_dpm = league_averages.get("damage_per_map", 1.0)
    league_kpm = league_averages.get("kills_per_map", 1.0)
    league_kd = league_averages.get("KD", 1.0)

    score = (dmg_per_map * 0.4) + (kpm * 0.4) + (kd * 0.2)
    league_score = (league_dpm * 0.4) + (league_kpm * 0.4) + (league_kd * 0.2) or 1.0

    ratio = score / league_score

    if ratio >= 1.50:
        strength = "Elite Slayer"
    elif ratio >= 1.25:
        strength = "Strong Slayer"
    elif ratio >= 1.00:
        strength = "Slayer"
    elif ratio >= 0.75:
        strength = "Below Average"
    else:
        strength = "Not a Slayer"

    return {
        "score_raw": score,
        "score_display": f"{score:.2f}",
        "strength": strength,
    }