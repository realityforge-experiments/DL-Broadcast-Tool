from rankings import load_career_db
from tags.objective_domination import compute_dom_objective


def matchup_storyline(teamA_players, teamB_players):
    """
    Composition-aware storyline generator.
    Accepts two lists of player entries (5 per team).
    """

    if not teamA_players or not teamB_players:
        return "Not enough selected players to generate a storyline."

    # --- Helper averages ---
    def avg_slayer(players):
        return sum(p.get("slayer_score_raw", 0.0) for p in players) / max(1, len(players))

    def avg_obj_payload(players):
        return sum(
            p.get("objective_payload_components", {}).get("push_time_norm", 0.0)
            for p in players
        ) / max(1, len(players))

    def avg_sharp(players):
        return sum(
            p.get("sharpshooter_components", {}).get("accuracy_norm", 0.0)
            for p in players
        ) / max(1, len(players))

    def avg_obj_dom(players):
        return sum(compute_dom_objective(p) for p in players) / max(1, len(players))
        
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

        

    # --- Compute team averages ---
    a_slayer = avg_slayer(teamA_players)
    b_slayer = avg_slayer(teamB_players)

    a_obj = avg_obj_payload(teamA_players)
    b_obj = avg_obj_payload(teamB_players)

    a_sharp = avg_sharp(teamA_players)
    b_sharp = avg_sharp(teamB_players)

    a_dom = avg_obj_dom(teamA_players)
    b_dom = avg_obj_dom(teamB_players)

    a_consistency = avg_consistency(teamA_players)
    b_consistency = avg_consistency(teamB_players)
    
    a_clutch = avg_clutch(teamA_players)
    b_clutch = avg_clutch(teamB_players)

    # --- Team names ---
    team_a = teamA_players[0].get("team", "Team A")
    team_b = teamB_players[0].get("team", "Team B")

    # --- Build storyline ---
    lines = []
    lines.append(f"MATCH STORYLINE — {team_a} vs {team_b}\n")

    # Slayer storyline
    if a_slayer > b_slayer:
        lines.append(f"{team_a} bring stronger slaying on paper.")
    elif b_slayer > a_slayer:
        lines.append(f"{team_b} bring stronger slaying on paper.")
    else:
        lines.append("Slaying power looks evenly matched.")

    # Payload storyline
    if a_obj > b_obj:
        lines.append(f"{team_a} have the edge in Payload objective presence.")
    elif b_obj > a_obj:
        lines.append(f"{team_b} have the edge in Payload objective presence.")
    else:
        lines.append("Payload objective presence looks evenly matched.")

    # Domination storyline
    if a_dom > b_dom:
        lines.append(f"{team_a} show stronger Domination objective capability.")
    elif b_dom > a_dom:
        lines.append(f"{team_b} show stronger Domination objective capability.")
    else:
        lines.append("Domination objective capability looks evenly matched.")
        
        
    # Consistency storyline    
    if a_consistency > b_consistency:
        lines.append(f"{team_a} bring steadier map-to-map performance.")
    elif b_consistency > a_consistency:
        lines.append(f"{team_b} bring steadier map-to-map performance.")
    else:
        lines.append("Both teams show similar consistency across maps.")    
        
    # Clutch Storyline    
    if a_clutch > b_clutch:
        lines.append(f"{team_a} show stronger clutch performance in high-pressure moments.")
    elif b_clutch > a_clutch:
        lines.append(f"{team_b} show stronger clutch performance in high-pressure moments.")
    else:
        lines.append("Both teams show similar clutch performance.")     
        

    # Sharpshooter storyline
    sharp_delta = a_sharp - b_sharp
    sharp_pct = sharp_delta * 100

    if sharp_delta > 0.02:
        lines.append(
            f"{team_a} bring a Sharpshooter Advantage of {sharp_pct:.1f}%, "
            f"landing more shots and converting more headshots than {team_b}."
        )
    elif sharp_delta < -0.02:
        lines.append(
            f"{team_b} hold a Sharpshooter Edge of {abs(sharp_pct):.1f}%, "
            f"which could punish {team_a} in long‑range duels."
        )
    else:
        lines.append(
            "Both teams are evenly matched in Sharpshooting, so aim consistency "
            "won’t be a deciding factor unless someone pops off."
        )

    return "\n".join(lines)