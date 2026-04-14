# ============================================================
# FALLBACK + EARLY SEASON WEIGHTING
# ------------------------------------------------------------
# Provides universal fallback logic for all tags:
#   current → career → league average → neutral baseline
# Also provides early-season blending to stabilize noisy stats.
# ============================================================

def get_stat_with_fallback(current, career, league_avg, neutral_baseline=0.5):
    """Universal fallback logic used by all tags."""
    if current is not None:
        return current
    if career is not None:
        return career
    if league_avg is not None:
        return league_avg
    return neutral_baseline


def blend_early_season(current_value, career_value, matches_played_current, ramp_matches=5):
    """Blend current season and career stats early in the season."""
    if matches_played_current <= 0:
        return career_value

    weight_current = min(matches_played_current / ramp_matches, 1.0)
    weight_career = 1.0 - weight_current

    return (current_value * weight_current) + (career_value * weight_career)