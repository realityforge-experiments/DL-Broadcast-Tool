from tags.tag_framework import build_tag_output

# ---------------------------------------------------------
# Payload Summary
# ---------------------------------------------------------

def payload_summary(tier, pct):
    if tier == "S":
        return f"Elite Payload driver — top {100 - pct:.0f}% in push efficiency and presence."
    if tier == "A":
        return "Strong Payload contributor with reliable push presence."
    if tier == "B":
        return "Above-average Payload impact."
    if tier == "C":
        return "Below-average Payload contribution."
    return "Minimal Payload presence or push impact."


# ---------------------------------------------------------
# Raw Payload Score (Career)
# ---------------------------------------------------------

def compute_payload_raw(pdata):
    """
    Computes a normalized 0–1 Payload Objective Specialist score.
    Components:
        - PresenceNorm: fraction of matches that were Payload
        - PushNorm: average push time normalized to 300s soft cap
        - PSINorm: damage-per-death survivability normalized
    """

    matches = pdata.get("matches", [])
    if not matches:
        return 0.0

    total_matches = len(matches)
    payload_matches = 0
    total_push = 0.0
    total_damage = 0.0
    total_deaths = 0

    for m in matches:
        push = m.get("PAY_PushTime", 0) or 0
        dmg = m.get("Damage", 0) or 0
        deaths = m.get("Deaths", 0) or 0

        if push > 0:
            payload_matches += 1
            total_push += push
            total_damage += dmg
            total_deaths += deaths

    if payload_matches == 0:
        return 0.0

    # Presence
    presence_norm = payload_matches / total_matches

    # Push time
    avg_push = total_push / payload_matches
    push_norm = min(avg_push / 300.0, 1.0)

    # Survivability (PSI)
    psi_raw = total_damage / (total_deaths + 1)
    psi_norm = psi_raw / (psi_raw + 300.0)

    # Weighted final score
    raw = (
        0.40 * push_norm +
        0.40 * presence_norm +
        0.20 * psi_norm
    )

    return max(0.0, min(1.0, raw))


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def compute_payload_tag(pdata, league_averages, payload_distribution):
    raw = compute_payload_raw(pdata)
    return build_tag_output(raw, payload_distribution, payload_summary)