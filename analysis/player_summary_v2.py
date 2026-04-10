def build_player_summary(player):
    """
    Builds a caster-ready summary block for a single player.
    Uses:
        - Slayer
        - Payload Objective
        - Sharpshooter
        - Consistency
        - Clutch
    """

    name = player.get("name", "Unknown Player")

    slayer = player.get("slayer", {})
    payload = player.get("objective_payload", {})
    sharp = player.get("sharpshooter", {})
    consistency = player.get("consistency", {})
    clutch = player.get("clutch", {})

    lines = []
    lines.append(f"{name}\n")

    # Slayer
    lines.append(f"Slayer: {slayer.get('tier', 'D')} ({slayer.get('pct', 0):.1f}%)")
    lines.append(f"  {slayer.get('summary', '')}")

    # Payload
    lines.append(f"\nPayload Objective: {payload.get('tier', 'D')} ({payload.get('pct', 0):.1f}%)")
    lines.append(f"  {payload.get('summary', '')}")

    # Sharpshooter
    lines.append(f"\nSharpshooter: {sharp.get('tier', 'D')} ({sharp.get('pct', 0):.1f}%)")
    lines.append(f"  {sharp.get('summary', '')}")

    # Consistency
    lines.append(f"\nConsistency: {consistency.get('tier', 'D')} ({consistency.get('pct', 0):.1f}%)")
    lines.append(f"  {consistency.get('summary', '')}")

    # Clutch
    lines.append(f"\nClutch: {clutch.get('tier', 'D')} ({clutch.get('pct', 0):.1f}%)")
    lines.append(f"  {clutch.get('summary', '')}")

    return "\n".join(lines)