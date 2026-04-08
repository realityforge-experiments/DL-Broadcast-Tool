# tags/sharpshooter.py

def compute_sharpshooter_for_career_player(stats):
    shots_fired = stats.get("shots", 0)
    damage = stats.get("damage_dealt", stats.get("damage", 0))
    shots_hit = stats.get("shots_hit", 0)
    headshots = stats.get("headshots", 0)

    if shots_fired <= 0:
        return {
            "accuracy": 0.0,
            "hs_rate": 0.0,
            "dps": 0.0,
            "score_raw": 0.0,
            "score_display": "0.00",
        }

    accuracy = shots_hit / shots_fired
    hs_rate = headshots / shots_hit if shots_hit > 0 else 0.0
    dps = damage / shots_fired

    score = (0.40 * accuracy) + (0.40 * hs_rate) + (0.20 * dps)

    return {
        "accuracy": accuracy,
        "hs_rate": hs_rate,
        "dps": dps,
        "score_raw": score,
        "score_display": f"{score:.2f}",
    }