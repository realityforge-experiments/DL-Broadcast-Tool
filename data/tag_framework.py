import bisect

# ---------------------------------------------------------
# Percentile + Tier Helpers
# ---------------------------------------------------------

def percentile_rank(value, distribution):
    """
    Returns percentile rank (0–100) of value within a sorted distribution list.
    """
    if not distribution:
        return 0.0

    idx = bisect.bisect_left(distribution, value)
    pct = (idx / len(distribution)) * 100
    return round(pct, 1)


def tier_from_percentile(pct):
    """
    Converts percentile into S/A/B/C/D tier.
    """
    if pct >= 90:
        return "S"
    elif pct >= 75:
        return "A"
    elif pct >= 50:
        return "B"
    elif pct >= 25:
        return "C"
    else:
        return "D"


# ---------------------------------------------------------
# Universal Tag Output Builder
# ---------------------------------------------------------

def build_tag_output(raw_score, distribution, summary_fn):
    """
    Standardizes tag output:
    - raw score (0–1)
    - percentile
    - tier
    - caster-friendly summary
    """
    raw_score = max(0.0, min(1.0, raw_score))

    pct = percentile_rank(raw_score, distribution)
    tier = tier_from_percentile(pct)
    summary = summary_fn(tier, pct)

    return {
        "raw": raw_score,
        "pct": pct,
        "tier": tier,
        "summary": summary
    }
    
    
# ============================================================
# CONSISTENCY TAG ADAPTER
# ------------------------------------------------------------
# Adapts the new ConsistencyResult object into the legacy
# tag_framework format expected by the UI + rankings.
# ============================================================

from tags.consistency import build_consistency_tag

def compute_consistency_tag(player_stats, distribution):
    """
    Adapter layer:
    - Extracts needed stats from player_stats
    - Calls the new Consistency tag builder
    - Returns raw score + summary_fn for tag_framework
    """

    # -----------------------------------------
    # Extract stats (0–1 normalized values)
    # -----------------------------------------
    floor_current = player_stats.get("floor_current")
    floor_career = player_stats.get("floor_career")
    floor_league = player_stats.get("floor_league")

    stability_current = player_stats.get("stability_current")
    stability_career = player_stats.get("stability_career")
    stability_league = player_stats.get("stability_league")

    average_current = player_stats.get("average_current")
    average_career = player_stats.get("average_career")
    average_league = player_stats.get("average_league")

    matches_played = player_stats.get("matches_played_current", 0)

    # -----------------------------------------
    # Build full ConsistencyResult object
    # -----------------------------------------
    result = build_consistency_tag(
        floor_current=floor_current,
        floor_career=floor_career,
        floor_league=floor_league,
        stability_current=stability_current,
        stability_career=stability_career,
        stability_league=stability_league,
        average_current=average_current,
        average_career=average_career,
        average_league=average_league,
        matches_played_current=matches_played,
        percentile=None  # tag_framework will compute this
    )

    # -----------------------------------------
    # Summary function for tag_framework
    # -----------------------------------------
    def summary_fn(tier, pct):
        return result.summary_short

    # -----------------------------------------
    # Return raw score + summary_fn
    # -----------------------------------------
    return result.normalized_score, summary_fn