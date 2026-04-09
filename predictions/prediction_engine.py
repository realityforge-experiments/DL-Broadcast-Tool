import math
from tags.objective_domination import compute_dom_objective_for_career_player

def logistic_win_chance(teamA_avg, teamB_avg, k=1.1):
    """Generic logistic win chance for all tags."""
    if max(teamA_avg, teamB_avg) == 0:
        return 50, 50

    edge = (teamB_avg - teamA_avg) / max(teamA_avg, teamB_avg)
    pB = 1 / (1 + math.exp(-k * edge))
    pA = 1 - pB

    return round(pA * 100), round(pB * 100)


def compute_tag_averages(teamA_players, teamB_players):
    """Compute all tag averages for both teams using career identity scores."""

    def avg_slayer(players):
        return sum(p.get("slayer_score_raw", 0.0) for p in players) / max(1, len(players))

    def avg_objpl(players):
        return sum(
            p.get("objective_payload_components", {}).get("payload_score_raw", 0.0)
            for p in players
        ) / max(1, len(players))

    def avg_objdom(players):
        return sum(
            compute_dom_objective_for_career_player(
                p.get("career_entry", {})
            ).get("dom_score_raw", 0.0)
            for p in players
        ) / max(1, len(players))

    def avg_sharp(players):
        return sum(
            p.get("sharpshooter_components", {}).get("accuracy_norm", 0.0)
            for p in players
        ) / max(1, len(players))

    def avg_consistency(players):
        return sum(
            p.get("consistency_components", {}).get("consistency_norm", 0.0)
            for p in players
        ) / max(1, len(players))

    def avg_clutch(players):
        return sum(
            p.get("clutch_components", {}).get("clutch_norm", 0.0)
            for p in players
        ) / max(1, len(players))

    return {
        "Slayer": (avg_slayer(teamA_players), avg_slayer(teamB_players)),
        "ObjPL": (avg_objpl(teamA_players), avg_objpl(teamB_players)),
        "ObjDOM": (avg_objdom(teamA_players), avg_objdom(teamB_players)),
        "Sharpshooter": (avg_sharp(teamA_players), avg_sharp(teamB_players)),
        "Consistency": (avg_consistency(teamA_players), avg_consistency(teamB_players)),
        "Clutch": (avg_clutch(teamA_players), avg_clutch(teamB_players)),
    }


def generate_predictions(teamA_players, teamB_players):
    """Full Option D prediction engine (modernized)."""

    team_a = teamA_players[0].get("team", "Team A")
    team_b = teamB_players[0].get("team", "Team B")

    # --- Compute averages ---
    avgs = compute_tag_averages(teamA_players, teamB_players)

    # --- Per-tag win chances ---
    per_tag = {}
    for tag, (a_avg, b_avg) in avgs.items():
        per_tag[tag] = logistic_win_chance(a_avg, b_avg)

    # --- Weighted overall prediction ---
    weights = {
        "Slayer": 0.30,
        "ObjPL": 0.25,
        "ObjDOM": 0.25,
        "Sharpshooter": 0.10,
        "Consistency": 0.05,
        "Clutch": 0.05,
    }

    overall_A = sum(per_tag[tag][0] * w for tag, w in weights.items())
    overall_B = sum(per_tag[tag][1] * w for tag, w in weights.items())

    # Normalize to 100%
    total = overall_A + overall_B
    if total > 0:
        overall_A = round((overall_A / total) * 100)
        overall_B = 100 - overall_A
    else:
        overall_A = overall_B = 50

    # --- Narrative summary ---
    narrative = []

    def add_line(tag, a, b):
        if a > b:
            narrative.append(f"{team_a} hold the edge in {tag}.")
        elif b > a:
            narrative.append(f"{team_b} hold the edge in {tag}.")

    for tag, (a_avg, b_avg) in avgs.items():
        add_line(tag, a_avg, b_avg)

    if overall_A > overall_B:
        narrative.append(f"Overall, {team_a} enter this matchup with a slight advantage.")
    elif overall_B > overall_A:
        narrative.append(f"Overall, {team_b} enter this matchup with a slight advantage.")
    else:
        narrative.append("Overall, this matchup looks extremely close.")

    # --- Build final text output ---
    lines = []
    lines.append(f"MATCH PREDICTIONS — {team_a} vs {team_b}\n")

    for tag, (pA, pB) in per_tag.items():
        lines.append(f"{tag} Win Chance: {team_a} {pA}% — {team_b} {pB}%")

    lines.append("\nOVERALL WIN CHANCE:")
    lines.append(f"{team_a} {overall_A}% — {team_b} {overall_B}%")

    lines.append("\nNARRATIVE SUMMARY:")
    lines.append(" ".join(narrative))

    return "\n".join(lines)