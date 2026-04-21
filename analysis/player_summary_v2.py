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

    def safe_pct(value):
        try:
            return float(value) if value is not None else 0.0
        except:
            return 0.0

    def safe_tier(value):
        return value if value not in (None, "", "None") else "D"

    name = player.get("name", "Unknown Player")

    slayer = player.get("slayer", {})
    payload = player.get("objective_payload", {})
    sharp = player.get("sharpshooter", {})
    consistency = player.get("consistency", {})
    clutch = player.get("clutch", {})

    lines = []
    lines.append(f"{name}\n")

    # Slayer
    lines.append(f"Slayer: {safe_tier(slayer.get('tier'))} ({safe_pct(slayer.get('pct')):.1f}%)")
    lines.append(f"  {slayer.get('summary', '')}")

    # Payload
    lines.append(f"\nPayload Objective: {safe_tier(payload.get('tier'))} ({safe_pct(payload.get('pct')):.1f}%)")
    lines.append(f"  {payload.get('summary', '')}")

    # Sharpshooter
    lines.append(f"\nSharpshooter: {safe_tier(sharp.get('tier'))} ({safe_pct(sharp.get('pct')):.1f}%)")
    lines.append(f"  {sharp.get('summary', '')}")

    # Consistency
    lines.append(f"\nConsistency: {safe_tier(consistency.get('tier'))} ({safe_pct(consistency.get('pct')):.1f}%)")
    lines.append(f"  {consistency.get('summary', '')}")

    # Clutch
    lines.append(f"\nClutch: {safe_tier(clutch.get('tier'))} ({safe_pct(clutch.get('pct')):.1f}%)")
    lines.append(f"  {clutch.get('summary', '')}")
    
    # Breaker
    lines.append(f"\nBreaker: {safe_tier(breaker.get('tier'))} ({safe_pct(breaker.get('pct')):.1f}%)")
    lines.append(f"  {breaker.get('summary', '')}")

    return "\n".join(lines)