from utils.safe_tag import safe_pct, safe_tier, safe_avg

# Caster‑friendly display names
DISPLAY_NAMES = {
    "slayer": "Slayer",
    "objective_payload": "Payload Specialist",
    "sharpshooter": "Sharpshooter",
    "consistency": "Consistency",
    "clutch": "Clutch",
    "anchor": "Anchor Specialist",
    "breaker": "Breaker",
}


def summarize_team_tags(team_players):
    """
    Aggregates tag tiers + percentiles for a team.
    Returns a dict with:
        - avg_pct
        - top_tier
        - tier counts
    """

    tags = ["slayer", "objective_payload", "sharpshooter",
            "consistency", "clutch", "anchor", "breaker"]

    summary = {}

    for tag in tags:
        pcts = []
        tiers = []

        for p in team_players:
            tag_data = p.get(tag, {})
            pcts.append(safe_pct(tag_data.get("pct")))
            tiers.append(safe_tier(tag_data.get("tier")))  # guaranteed valid tier

        summary[tag] = {
            "avg_pct": safe_avg(pcts),  # guaranteed numeric
            "top_tier": max(tiers, key=lambda t: "SABCD".index(t)),
            "count_S": tiers.count("S"),
            "count_A": tiers.count("A"),
            "count_B": tiers.count("B"),
            "count_C": tiers.count("C"),
            "count_D": tiers.count("D"),
        }

    return summary


def classify_team_style(summary):
    """
    Produces a high-level team style classification based on tag strengths.
    """

    slayer = summary["slayer"]["avg_pct"]
    payload = summary["objective_payload"]["avg_pct"]
    sharpshooter = summary["sharpshooter"]["avg_pct"]
    consistency = summary["consistency"]["avg_pct"]
    clutch = summary["clutch"]["avg_pct"]
    anchor = summary["anchor"]["avg_pct"]

    # Primary style selection
    primary = max(
        {
            "Slayer-heavy": slayer,
            "Objective-focused": payload,
            "Precision/Sharpshooter": sharpshooter,
            "Stable/Consistent": consistency,
            "High-pressure/Clutch": clutch,
            "Anchor/Support": anchor,
        }.items(),
        key=lambda x: x[1]
    )[0]

    # Weakness detection
    weaknesses = []
    if slayer < 40:
        weaknesses.append("low elimination pressure")
    if payload < 40:
        weaknesses.append("weak objective presence")
    if sharpshooter < 40:
        weaknesses.append("below-average accuracy")
    if consistency < 40:
        weaknesses.append("inconsistent match-to-match output")
    if clutch < 40:
        weaknesses.append("poor high-pressure performance")
    if anchor < 40:
        weaknesses.append("weak defensive backbone / low anchor stability")

    return primary, weaknesses


def generate_team_identity_block(team_players, team_name="Team"):
    """
    Returns a structured identity block dict for a team.
    GUI or OBS formatter will convert this into text.
    """

    summary = summarize_team_tags(team_players)
    primary_style, weaknesses = classify_team_style(summary)

    # Strengths list
    strengths = []
    for tag, data in summary.items():
        if data["avg_pct"] >= 60:
            display = DISPLAY_NAMES.get(tag, tag.replace("_", " ").title())
            strengths.append(
                f"Strong {display} ({data['top_tier']} Tier)"
            )

    # Tag breakdown
    tag_block = {}
    for tag, data in summary.items():
        tag_block[tag] = {
            "avg_pct": data["avg_pct"],
            "tier": data["top_tier"],
        }

    return {
        "team_name": team_name,
        "team_style": primary_style,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "tags": tag_block,
    }


def format_team_identity(identity_data):
    """
    Converts the identity block dict into a readable text block.
    Used by GUI and OBS exporters.
    """

    lines = []

    lines.append(f"Team: {identity_data['team_name']}")
    lines.append(f"Playstyle: {identity_data['team_style']}")
    lines.append("")

    # Strengths
    lines.append("Strengths:")
    if identity_data["strengths"]:
        for s in identity_data["strengths"]:
            lines.append(f"  - {s}")
    else:
        lines.append("  - None identified")

    lines.append("")

    # Weaknesses
    lines.append("Weaknesses:")
    if identity_data["weaknesses"]:
        for w in identity_data["weaknesses"]:
            lines.append(f"  - {w}")
    else:
        lines.append("  - None identified")

    lines.append("")
    lines.append("Tag Breakdown:")

    for tag, data in identity_data["tags"].items():
        name = DISPLAY_NAMES.get(tag, tag.replace("_", " ").title())
        lines.append(
            f"  - {name}: {data['tier']} Tier (avg {data['avg_pct']:.1f} percentile)"
        )

    return "\n".join(lines)