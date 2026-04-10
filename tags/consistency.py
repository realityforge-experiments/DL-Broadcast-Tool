import math
from tags.tag_framework import build_tag_output

# ---------------------------------------------------------
# Raw Consistency Score (Robust)
# ---------------------------------------------------------

def compute_consistency_raw(matches):
    """
    Computes a normalized 0–1 consistency score based on
    match-to-match stability in KD, damage, and accuracy.
    """

    if not matches:
        return 0.05  # minimum floor

    perf = []

    for m in matches:
        kills = m.get("Kills", 0)
        deaths = m.get("Deaths", 0)
        damage = m.get("Damage", 0)
        shots = m.get("Shots", 0)
        shots_hit = m.get("ShotsHit", 0)

        kd = kills / max(1, deaths)
        acc = shots_hit / shots if shots > 0 else 0.0

        # Normalize components into comparable ranges
        kd_norm = min(kd / 5.0, 1.0)          # KD 0–5
        dmg_norm = min(damage / 3000.0, 1.0)  # Damage 0–3000
        acc_norm = acc                        # Already 0–1

        # Composite performance score per match
        perf_score = (0.4 * kd_norm) + (0.4 * dmg_norm) + (0.2 * acc_norm)
        perf.append(perf_score)

    # Variance of performance
    if len(perf) <= 1:
        return 0.25  # floor for single-match players

    mean = sum(perf) / len(perf)
    var = sum((p - mean) ** 2 for p in perf) / len(perf)
    std = math.sqrt(var)

    # Smoothing
    std = max(std, 0.05)

    # Convert std into consistency score
    raw = 1.0 / (1.0 + std)

    # Soft clamp
    return max(0.05, min(raw, 1.0))


# ---------------------------------------------------------
# Summary
# ---------------------------------------------------------

def consistency_summary(tier, pct):
    if tier == "S":
        return f"Ultra-stable performer — top {100 - pct:.0f}% in match-to-match consistency."
    if tier == "A":
        return "Very consistent across matches."
    if tier == "B":
        return "Above-average consistency."
    if tier == "C":
        return "Inconsistent performance."
    return "Highly volatile match-to-match output."


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def compute_consistency(matches):
    raw = compute_consistency_raw(matches)
    return raw, {"consistency_norm": raw}


def compute_consistency_tag(components, consistency_distribution):
    raw = components.get("consistency_norm", 0.0)
    return build_tag_output(raw, consistency_distribution, consistency_summary)