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