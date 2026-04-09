import math

def compute_consistency(matches):
    """
    Compute consistency based on per-match performance stability.
    Uses:
      - KD per match
      - Damage per match
      - Accuracy per match
    """

    if not matches:
        return 0.0, {
            "match_count": 0,
            "kd_std": 0.0,
            "dmg_std": 0.0,
            "acc_std": 0.0,
            "consistency_norm": 0.0,
        }

    kds = []
    dmgs = []
    accs = []

    for m in matches:
        kills = m["Kills"]
        deaths = m["Deaths"]
        damage = m["Damage"]
        shots = m["Shots"]
        shots_hit = m["ShotsHit"]

        kd = kills / max(1, deaths)
        acc = shots_hit / shots if shots > 0 else 0.0

        kds.append(kd)
        dmgs.append(damage)
        accs.append(acc)

    def std(values):
        if len(values) <= 1:
            return 0.0
        mean = sum(values) / len(values)
        var = sum((v - mean) ** 2 for v in values) / len(values)
        return math.sqrt(var)

    kd_std = std(kds)
    dmg_std = std(dmgs)
    acc_std = std(accs)

    # Lower variance = more consistent
    # Normalize into a 0–1 score
    raw = 1.0 / (1.0 + kd_std + dmg_std + acc_std)

    components = {
        "match_count": len(matches),
        "kd_std": kd_std,
        "dmg_std": dmg_std,
        "acc_std": acc_std,
        "consistency_norm": raw,
    }

    return raw, components