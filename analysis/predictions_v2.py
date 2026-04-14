from analysis.team_identity_v2 import summarize_team_tags, classify_team_style


def compute_team_power_score(summary):
    """
    Converts team tag percentiles into a single weighted power score.
    Weights reflect real match impact:
        Slayer:        30%
        Objective:     25%
        Consistency:   20%
        Clutch:        15%
        Sharpshooter:  10%
    """

    return (
        summary["slayer"]["avg_pct"] * 0.30 +
        summary["objective_payload"]["avg_pct"] * 0.25 +
        summary["consistency"]["avg_pct"] * 0.20 +
        summary["clutch"]["avg_pct"] * 0.15 +
        summary["sharpshooter"]["avg_pct"] * 0.10
    )


def generate_prediction(teamA_players, teamB_players, teamA_name="Team A", teamB_name="Team B"):
    """
    Generates a caster-ready prediction block using:
    - Team Identity 2.0
    - Weighted tag power scores
    - Style classification
    - Strength/weakness contrast
    """

    # -----------------------------------------
    # 1. Summaries
    # -----------------------------------------
    A = summarize_team_tags(teamA_players)
    B = summarize_team_tags(teamB_players)

    # -----------------------------------------
    # 2. Power scores
    # -----------------------------------------
    A_power = compute_team_power_score(A)
    B_power = compute_team_power_score(B)

    # -----------------------------------------
    # 3. Style classification
    # -----------------------------------------
    A_style, A_weak = classify_team_style(A)
    B_style, B_weak = classify_team_style(B)

    # -----------------------------------------
    # 4. Determine favorite
    # -----------------------------------------
    diff = A_power - B_power

    if abs(diff) < 5:
        favorite = "Too close to call — this matchup is statistically even."
    elif diff > 0:
        favorite = f"{teamA_name} are favored based on stronger overall tag profile."
    else:
        favorite = f"{teamB_name} are favored based on stronger overall tag profile."

    # -----------------------------------------
    # 5. Build prediction text
    # -----------------------------------------
    lines = []
    lines.append("MATCH PREDICTION\n")

    lines.append(f"{teamA_name} Power Score: {A_power:.1f}")
    lines.append(f"{teamB_name} Power Score: {B_power:.1f}\n")

    lines.append(f"{teamA_name} Style: {A_style}")
    lines.append(f"{teamB_name} Style: {B_style}\n")

    lines.append("Key Weaknesses:")
    lines.append(f"  {teamA_name}: {', '.join(A_weak) if A_weak else 'No major weaknesses'}")
    lines.append(f"  {teamB_name}: {', '.join(B_weak) if B_weak else 'No major weaknesses'}\n")

    # -----------------------------------------
    # 6. Consistency comparison (new)
    # -----------------------------------------
    A_cons = A["consistency"]["avg_pct"]
    B_cons = B["consistency"]["avg_pct"]

    if abs(A_cons - B_cons) < 5:
        cons_line = "Both teams show similar consistency across the season."
    elif A_cons > B_cons:
        cons_line = f"{teamA_name} have been the more stable team, with stronger match-to-match consistency."
    else:
        cons_line = f"{teamB_name} have been the more stable team, with stronger match-to-match consistency."

    lines.append("\nConsistency Check:")
    lines.append(f"  {cons_line}\n")

    # -----------------------------------------
    # 7. Final prediction line
    # -----------------------------------------
    lines.append("Prediction:")
    lines.append(f"  {favorite}")

    return "\n".join(lines)