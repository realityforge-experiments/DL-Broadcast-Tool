# ============================================================
# CONSISTENCY TAG
# ------------------------------------------------------------
# Template tag for the entire system.
# Uses:
#   - fallback logic
#   - early-season blending
#   - normalization
#   - tier mapping
#   - summary generation
#   - spotlight extras
# ============================================================

from dataclasses import dataclass
from utils.fallback import get_stat_with_fallback, blend_early_season
from utils.tiers import map_score_to_tier
from utils.summaries import build_consistency_summaries


# ------------------------------------------------------------
# Data structures
# ------------------------------------------------------------

@dataclass
class ConsistencyComponents:
    floor: float
    stability: float
    average_performance: float


@dataclass
class ConsistencyResult:
    raw_score: float
    normalized_score: float
    percentile: float | None
    tier: str
    components: ConsistencyComponents
    summary_short: str
    summary_long: str
    storyline_hook: str
    identity_signal: str
    extras: dict


# ------------------------------------------------------------
# Core formula (your original formula)
# ------------------------------------------------------------

def compute_consistency_score(components: ConsistencyComponents) -> float:
    return (
        components.floor * 0.40 +
        components.stability * 0.40 +
        components.average_performance * 0.20
    )


# ------------------------------------------------------------
# Main builder
# ------------------------------------------------------------

def build_consistency_tag(
    *,
    floor_current,
    floor_career,
    floor_league,
    stability_current,
    stability_career,
    stability_league,
    average_current,
    average_career,
    average_league,
    matches_played_current,
    percentile=None
) -> ConsistencyResult:

    # --- FALLBACK ---
    floor_raw = get_stat_with_fallback(floor_current, floor_career, floor_league)
    stability_raw = get_stat_with_fallback(stability_current, stability_career, stability_league)
    average_raw = get_stat_with_fallback(average_current, average_career, average_league)

    # --- EARLY SEASON BLENDING ---
    floor_value = blend_early_season(floor_raw, floor_career or floor_raw, matches_played_current)
    stability_value = blend_early_season(stability_raw, stability_career or stability_raw, matches_played_current)
    average_value = blend_early_season(average_raw, average_career or average_raw, matches_played_current)

    # --- COMPONENTS ---
    components = ConsistencyComponents(
        floor=floor_value,
        stability=stability_value,
        average_performance=average_value
    )

    # --- SCORE ---
    raw_score = compute_consistency_score(components)
    normalized_score = max(0.0, min(1.0, raw_score))

    # --- TIER + SUMMARIES ---
    tier = map_score_to_tier(normalized_score)
    summary_short, summary_long, storyline, identity = build_consistency_summaries(
        normalized_score, components, tier
    )

    # --- EXTRAS (Spotlight) ---
    extras = {
        "floor_value": floor_value,
        "stability_value": stability_value,
        "average_value": average_value,
        "matches_played_current": matches_played_current,
    }

    return ConsistencyResult(
        raw_score=raw_score,
        normalized_score=normalized_score,
        percentile=percentile,
        tier=tier,
        components=components,
        summary_short=summary_short,
        summary_long=summary_long,
        storyline_hook=storyline,
        identity_signal=identity,
        extras=extras
    )