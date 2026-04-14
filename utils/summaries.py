# ============================================================
# SUMMARY GENERATION
# ------------------------------------------------------------
# Builds caster-friendly summaries for tags.
# ============================================================

def build_consistency_summaries(score, components, tier):
    summary_short = (
        f"Consistency: {score:.2f} ({tier} tier). "
        f"Floor {components.floor:.2f}, stability {components.stability:.2f}."
    )

    summary_long = (
        f"This player shows a {tier}-tier level of consistency ({score:.2f}). "
        f"Their floor ({components.floor:.2f}) shows how rarely they drop off, "
        f"while stability ({components.stability:.2f}) reflects match-to-match variance. "
        f"Their average performance ({components.average_performance:.2f}) "
        f"sets expectations for today's matchup."
    )

    if tier in ("S", "A"):
        storyline = "A rock for their team — expect dependable output every map."
        identity = "Anchor"
    elif tier == "B":
        storyline = "Generally reliable with occasional swings."
        identity = "Steady"
    elif tier == "C":
        storyline = "Inconsistent — performance varies significantly."
        identity = "Volatile"
    else:
        storyline = "Highly unpredictable — a true wildcard."
        identity = "Wildcard"

    return summary_short, summary_long, storyline, identity