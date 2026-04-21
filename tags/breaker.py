# ============================================================
# BREAKER TAG (v1 - Mode Safe)
# ------------------------------------------------------------
# Breaker measures offensive disruption using only stats that
# exist for BOTH Payload and Domination:
#
#   - Damage per map
#   - Kills per map
#
# No captures, no counters, no streaks, no timing.
# ============================================================

def compute_breaker_raw(damage_per_map, kills_per_map):
    """
    Computes the raw Breaker score (0–infinity).
    This is later normalized by league distribution.

    Breaker v1:
        60% damage pressure
        40% kill pressure
    """
    return (0.60 * damage_per_map) + (0.40 * kills_per_map)


def build_breaker_summary(tier, pct):
    """
    Returns caster-friendly summary text.
    """
    if tier == "S":
        return "One of the league’s top offensive disruptors."
    if tier == "A":
        return "A strong pressure player who cracks open defenses."
    if tier == "B":
        return "Provides steady offensive pressure."
    if tier == "C":
        return "Occasional pressure but inconsistent impact."
    return "Low offensive disruption output."