import math

# ---------------------------------------------------------
# 1. CAREER PAYLOAD OBJECTIVE SPECIALIST (MODERNIZED)
# ---------------------------------------------------------

def compute_payload_objective_for_career_player(pdata, league_averages=None):
    """
    Modernized career Payload Objective Specialist score.
    Mirrors the structure of Domination's career tag.

    Components:
    - PresenceNorm: fraction of matches that were Payload
    - PushNorm: average push time normalized to 300s soft cap
    - PSINorm: damage-per-death survivability normalized

    Final score:
        0.40 * PushNorm
      + 0.40 * PresenceNorm
      + 0.20 * PSINorm
    """

    matches = pdata.get("matches", [])
    if not matches:
        return {
            "payload_matches": 0,
            "total_push_time": 0.0,
            "avg_push_time": 0.0,
            "presence_norm": 0.0,
            "push_norm": 0.0,
            "psi_norm": 0.0,
            "payload_score_raw": 0.0,
            "payload_score_display": "0.00",
        }

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
        return {
            "payload_matches": 0,
            "total_push_time": 0.0,
            "avg_push_time": 0.0,
            "presence_norm": 0.0,
            "push_norm": 0.0,
            "psi_norm": 0.0,
            "payload_score_raw": 0.0,
            "payload_score_display": "0.00",
        }

    # --- PresenceNorm ---
    presence_norm = payload_matches / total_matches

    # --- PushNorm ---
    avg_push = total_push / payload_matches
    push_norm = min(avg_push / 300.0, 1.0)

    # --- PSINorm ---
    psi_raw = total_damage / (total_deaths + 1)
    psi_norm = psi_raw / (psi_raw + 300.0)

    # --- Final Score ---
    raw = (0.40 * push_norm) + (0.40 * presence_norm) + (0.20 * psi_norm)

    return {
        "payload_matches": payload_matches,
        "total_push_time": total_push,
        "avg_push_time": avg_push,
        "presence_norm": presence_norm,
        "push_norm": push_norm,
        "psi_norm": psi_norm,
        "payload_score_raw": raw,
        "payload_score_display": f"{raw:.2f}",
    }


# ---------------------------------------------------------
# 2. MATCH-BASED PAYLOAD OBJECTIVE SPECIALIST (MODERNIZED)
# ---------------------------------------------------------

def compute_payload_objective_for_match_player(p):
    """
    Extract match-level Payload stats for a single player.
    Normalized naming for consistency.
    """

    push = p.get("PAY_PushTime", 0) or 0
    dmg = p.get("damage", p.get("Damage", 0)) or 0
    deaths = p.get("deaths", p.get("Deaths", 0)) or 0

    return {
        "push_time": push,
        "damage": dmg,
        "deaths": deaths,
    }


# ---------------------------------------------------------
# 3. TEAM SCORE CALCULATION (MATCH-BASED, MODERNIZED)
# ---------------------------------------------------------

def compute_payload_objective_team_scores(team_entries):
    """
    team_entries = list of (pid, career_entry, match_player)

    Components:
    - Presence: push_time / team_total_push
    - PushNorm: push_time / 300s soft cap
    - PSINorm: damage-per-death normalized

    Final score:
        0.40 * Presence
      + 0.40 * PushNorm
      + 0.20 * PSINorm
    """

    # Total team push time
    team_push = sum(mp.get("PAY_PushTime", 0) or 0 for _, _, mp in team_entries)
    if team_push <= 0:
        team_push = 1  # avoid div-by-zero

    scores = {}

    for pid, entry, mp in team_entries:
        push = mp.get("PAY_PushTime", 0) or 0
        dmg = mp.get("damage", mp.get("Damage", 0)) or 0
        deaths = mp.get("deaths", mp.get("Deaths", 0)) or 0

        # --- Presence ---
        presence = push / team_push

        # --- PushNorm ---
        push_norm = min(push / 300.0, 1.0)

        # --- PSINorm ---
        psi_raw = dmg / (deaths + 1)
        psi_norm = psi_raw / (psi_raw + 300.0)

        # --- Final Score ---
        score = (0.40 * presence) + (0.40 * push_norm) + (0.20 * psi_norm)

        scores[pid] = round(score, 4)

    return scores