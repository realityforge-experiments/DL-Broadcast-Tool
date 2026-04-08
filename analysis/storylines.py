from team_identity import team_identity

def matchup_storyline(team_a: str, team_b: str) -> str:
    """Generate rich, caster-ready storyline with talking points and predictive flavor."""
    A = team_identity(team_a)
    B = team_identity(team_b)

    story = [f"🎙️ MATCH STORYLINE: {team_a} vs {team_b}\n"]

    # Slayer Power
    slayer_a = A["tag_counts"].get("Slayer", 0)
    slayer_b = B["tag_counts"].get("Slayer", 0)
    if slayer_a > slayer_b:
        story.append(f"• {team_a} brings **superior slayer firepower** ({slayer_a} tagged Slayers vs {slayer_b}).")
    elif slayer_b > slayer_a:
        story.append(f"• {team_b} brings **superior slayer firepower** ({slayer_b} tagged Slayers vs {slayer_a}).")
    else:
        story.append(f"• Both teams have equal slayer power — this could come down to execution.")

    # Objective Control
    obj_a = A["tag_counts"].get("Objective Specialist", 0)
    obj_b = B["tag_counts"].get("Objective Specialist", 0)
    if obj_a > obj_b:
        story.append(f"• {team_a} has **deeper objective presence** and map control potential.")
    elif obj_b > obj_a:
        story.append(f"• {team_b} has **deeper objective presence** and map control potential.")

    # Anchor / Stability
    if A["tag_counts"].get("Anchor", 0) >= 1 and B["tag_counts"].get("Anchor", 0) == 0:
        story.append(f"• {team_a} has a clear **anchor advantage** — expect a rock-solid backline.")
    elif B["tag_counts"].get("Anchor", 0) >= 1 and A["tag_counts"].get("Anchor", 0) == 0:
        story.append(f"• {team_b} has a clear **anchor advantage** — expect a rock-solid backline.")

    # Experience / Rookie Factor
    vet_a = A["tag_counts"].get("Veteran", 0)
    rook_a = A["tag_counts"].get("Rookie", 0)
    vet_b = B["tag_counts"].get("Veteran", 0)
    rook_b = B["tag_counts"].get("Rookie", 0)
    if rook_a >= 2 and vet_b >= 2:
        story.append(f"• {team_a} is young and hungry — {team_b} brings veteran experience. Classic youth vs experience matchup.")

    # Direct Exploit Lines
    if "Weak objective presence" in A["weaknesses"] and "Strong objective depth" in B["strengths"]:
        story.append(f"🔥 {team_b} is perfectly positioned to **exploit {team_a}'s weak objective play**.")
    if "Weak objective presence" in B["weaknesses"] and "Strong objective depth" in A["strengths"]:
        story.append(f"🔥 {team_a} is perfectly positioned to **exploit {team_b}'s weak objective play**.")

    # Final prediction flavor
    story.append("\n**Caster Talking Points Summary:**")
    story.append(f"• Watch for early slayer duels — the team that wins the Slayer battle usually controls the pace.")
    story.append(f"• Objective maps will heavily favor the side with more Objective Specialists.")
    story.append(f"• This matchup has high upset potential if the younger team executes cleanly.")

    return "\n".join(story)