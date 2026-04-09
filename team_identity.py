from rankings import load_career_db
from tags.objective_domination import (
    compute_dom_objective_for_career_player,
    compute_dom_objective_for_match_player,
    compute_dom_objective_team_scores
)


def generate_team_identity(player_list):
    """
    Returns a dictionary of team identity scores based on the average
    identity-tag components of the SELECTED PLAYERS ONLY.
    """

    if not player_list:
        return None

    # --- Helper functions for each identity tag ---
    def avg_slayer(players):
        return sum(p.get("slayer_score_raw", 0.0) for p in players) / max(1, len(players))

    def avg_payload(players):
        return sum(
            p.get("objective_payload_components", {}).get("payload_score_raw", 0.0)
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

    def avg_sharp(players):
        return sum(
            p.get("sharpshooter_components", {}).get("accuracy_norm", 0.0)
            for p in players
        ) / max(1, len(players))

    def avg_objdom(players):
        return sum(
            compute_dom_objective_for_career_player(
                p.get("career_entry", {})
            ).get("dom_score_raw", 0.0)
            for p in players
        ) / max(1, len(players))

    # --- Compute identity scores ---
    identity = {
        "slayer_score": avg_slayer(player_list),
        "payload_score": avg_payload(player_list),
        "consistency_score": avg_consistency(player_list),
        "clutch_score": avg_clutch(player_list),
        "sharpshooter_score": avg_sharp(player_list),
        "objdom_score": avg_objdom(player_list),
    }

    return identity


def compare_team_identity(teamA_players, teamB_players):
    a = generate_team_identity(teamA_players)
    b = generate_team_identity(teamB_players)

    if a is None or b is None:
        return "Not enough data to generate team identity comparison."

    team_a_name = teamA_players[0].get("team", "Team A")
    team_b_name = teamB_players[0].get("team", "Team B")

    summary = []

    # --- Slayer ---
    if a["slayer_score"] > b["slayer_score"]:
        summary.append(f"{team_a_name} lean slayer-heavy.")
    elif b["slayer_score"] > a["slayer_score"]:
        summary.append(f"{team_b_name} lean slayer-heavy.")

    # --- Payload Objective ---
    if a["payload_score"] > b["payload_score"]:
        summary.append(f"{team_a_name} show stronger Payload objective focus.")
    elif b["payload_score"] > a["payload_score"]:
        summary.append(f"{team_b_name} show stronger Payload objective focus.")

    # --- Domination Objective ---
    if a["objdom_score"] > b["objdom_score"]:
        summary.append(f"{team_a_name} show stronger Domination objective presence.")
    elif b["objdom_score"] > a["objdom_score"]:
        summary.append(f"{team_b_name} show stronger Domination objective presence.")

    # --- Consistency ---
    if a["consistency_score"] > b["consistency_score"]:
        summary.append(f"{team_a_name} are the steadier team.")
    elif b["consistency_score"] > a["consistency_score"]:
        summary.append(f"{team_b_name} are the steadier team.")

    # --- Clutch ---
    if a["clutch_score"] > b["clutch_score"]:
        summary.append(f"{team_a_name} excel in clutch situations.")
    elif b["clutch_score"] > a["clutch_score"]:
        summary.append(f"{team_b_name} excel in clutch situations.")

    # --- Sharpshooter ---
    if a["sharpshooter_score"] > b["sharpshooter_score"]:
        summary.append(f"{team_a_name} bring stronger aim and headshot conversion.")
    elif b["sharpshooter_score"] > a["sharpshooter_score"]:
        summary.append(f"{team_b_name} bring stronger aim and headshot conversion.")

    return " ".join(summary)