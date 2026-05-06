# storylines.py (Modernized & GUI-Compatible)

from analysis.team_identity_v2 import generate_team_identity_block
from analysis.team_identity_v2 import summarize_team_tags

__all__ = ["matchup_storyline", "generate_storyline"]


# ---------------------------------------------------------
# Team Tag Aggregation
# ---------------------------------------------------------

from utils.safe_tag import safe_pct, safe_tier, safe_avg

def summarize_team_tags(team_players):
    """
    Aggregates tag tiers + percentiles for a team.
    """

    tags = [
        "slayer",
        "objective_payload",
        "objective_domination",
        "sharpshooter",
        "consistency",
        "clutch",
        "anchor",
        "breaker",
    ]

    summary = {}

    for tag in tags:
        pcts = []
        tiers = []

        for p in team_players:
            tag_data = p.get(tag, {})
            pcts.append(safe_pct(tag_data.get("pct")))
            tiers.append(safe_tier(tag_data.get("tier")))

        # -----------------------------
        # FIX: safe top-tier calculation
        # -----------------------------
        valid_tiers = [t for t in tiers if t in "SABCD"]
        from data.tag_framework import tier_from_percentile
        top_tier = tier_from_percentile(safe_avg(pcts)) # Map the average pct to a tier

        summary[tag] = {
            "avg_pct": safe_avg(pcts),
            "top_tier": top_tier,
            "count_S": tiers.count("S"),
            "count_A": tiers.count("A"),
            "count_B": tiers.count("B"),
            "count_C": tiers.count("C"),
            "count_D": tiers.count("D"),
        }

    return summary


# ---------------------------------------------------------
# Team Strength Comparison
# ---------------------------------------------------------

def compare_team_strengths(teamA, teamB, team_a_name, team_b_name):
    """
    Compares two team tag summaries and returns storyline points.
    """

    storyline = []

    tags = {
        "slayer": "Slayer (Elimination Pressure)",
        "objective_payload": "Payload Objective",
        "objective_domination": "Domination Objective",
        "sharpshooter": "Sharpshooter (Accuracy)",
        "consistency": "Consistency (Stability)",
        "clutch": "Clutch (High-Pressure Performance)",
        "anchor": "Anchor (Defensive Stability)",
        "breaker": "Breaker (Offensive Disruption)",
    }

    for tag, label in tags.items():
        a = teamA[tag]["avg_pct"]
        b = teamB[tag]["avg_pct"]

        diff = a - b
        
        
        # Custom storyline for Anchor
        if tag == "anchor":
            if abs(diff) < 5:
                storyline.append("Both teams are evenly matched in defensive stability.")
            elif diff > 0:
                storyline.append(f"{team_a_name} have stronger defensive stability, surviving longer and preventing collapses.")
            else:
                storyline.append(f"{team_b_name} have stronger defensive stability, giving them an edge in long fights.")
            continue 
            
        # Generic storyline for all other tags
        if abs(diff) < 5:
            storyline.append(f"Both teams are evenly matched in {label}.")
        elif diff > 0:
            storyline.append(f"{team_a_name} hold an advantage in {label}.")
        else:
            storyline.append(f"{team_b_name} hold an advantage in {label}.")

    return storyline


# ---------------------------------------------------------
# Main Storyline Generator
# ---------------------------------------------------------

def generate_storyline(teamA_players, teamB_players):
    """
    Generates a full caster-ready storyline block.
    """

    # Extract real team names
    team_a_name = teamA_players[0].get("team", "Team A")
    team_b_name = teamB_players[0].get("team", "Team B")

    # 1. Summaries
    A = summarize_team_tags(teamA_players)
    B = summarize_team_tags(teamB_players)

    # 2. Strength comparison
    matchup_points = compare_team_strengths(A, B, team_a_name, team_b_name)

    # 3. Identify elite players
    elite_A = [p["name"] for p in teamA_players if p.get("slayer", {}).get("tier") == "S"]
    elite_B = [p["name"] for p in teamB_players if p.get("slayer", {}).get("tier") == "S"]

    # 4. Build storyline text
    lines = []

    lines.append(f"MATCH STORYLINE — {team_a_name} vs {team_b_name}\n")

    # Team A identity
    lines.append(f"{team_a_name} Identity:")
    for tag, data in A.items():
        lines.append(
            f"  - {tag.replace('_', ' ').title()}: "
            f"{data['top_tier']} Tier (avg {data['avg_pct']:.1f} percentile)"
        )

    lines.append("")

    # Team B identity
    lines.append(f"{team_b_name} Identity:")
    for tag, data in B.items():
        lines.append(
            f"  - {tag.replace('_', ' ').title()}: "
            f"{data['top_tier']} Tier (avg {data['avg_pct']:.1f} percentile)"
        )

    lines.append("")

    # Elite players
    if elite_A:
        lines.append(f"{team_a_name} Elite Players: {', '.join(elite_A)}")
    if elite_B:
        lines.append(f"{team_b_name} Elite Players: {', '.join(elite_B)}")

    lines.append("")

    # Matchup points
    lines.append("Matchup Breakdown:")
    for point in matchup_points:
        lines.append(f"  - {point}")

    return "\n".join(lines)


# ---------------------------------------------------------
# Legacy Wrapper (GUI expects this exact name)
# ---------------------------------------------------------

def matchup_storyline(teamA_players, teamB_players):
    """
    Legacy wrapper for GUI compatibility.
    """
    return generate_storyline(teamA_players, teamB_players)