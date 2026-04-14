# ============================================================
# TIER MAPPING
# ------------------------------------------------------------
# Converts normalized tag scores (0–1) into caster-friendly tiers.
# ============================================================

def map_score_to_tier(score: float) -> str:
    if score >= 0.90:
        return "S"
    if score >= 0.75:
        return "A"
    if score >= 0.60:
        return "B"
    if score >= 0.45:
        return "C"
    return "D"