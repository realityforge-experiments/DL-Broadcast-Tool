from team_identity import team_identity

def matchup_storyline(team_a, team_b):
    A = team_identity(team_a)
    B = team_identity(team_b)

    story = []

    story.append(f"MATCH STORYLINE: {team_a} vs {team_b}\n")

    # Style comparison
    if A["tag_counts"].get("Slayer", 0) > B["tag_counts"].get("Slayer", 0):
        story.append(f"{team_a} brings stronger slayer power.")
    elif B["tag_counts"].get("Slayer", 0) > A["tag_counts"].get("Slayer", 0):
        story.append(f"{team_b} brings stronger slayer power.")

    if A["tag_counts"].get("Objective Specialist", 0) > B["tag_counts"].get("Objective Specialist", 0):
        story.append(f"{team_a} has deeper objective presence.")
    elif B["tag_counts"].get("Objective Specialist", 0) > A["tag_counts"].get("Objective Specialist", 0):
        story.append(f"{team_b} has deeper objective presence.")

    # Strength vs weakness
    if "Weak objective presence" in A["weaknesses"] and "Strong objective depth" in B["strengths"]:
        story.append(f"{team_b} may exploit {team_a}'s weak objective play.")

    if "Weak objective presence" in B["weaknesses"] and "Strong objective depth" in A["strengths"]:
        story.append(f"{team_a} may exploit {team_b}'s weak objective play.")

    return "\n".join(story)