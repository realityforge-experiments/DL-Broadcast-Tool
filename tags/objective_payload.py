import math


def compute_payload_objective_for_career_player(p, league_averages):
    career = p["career"]
    derived = p["derived"]

    push_time_total = career.get("push_time", 0) or 0
    damage = career.get("damage", 0) or 0
    deaths = career.get("deaths", 0) or 0
    push_time_per_season = derived.get("push_time_per_season", 0) or 0

    # Push Survivability Index (PSI)
    # PSI = Damage / (Deaths + 1) * 1 / sqrt(PushTime + 1)
    psi = 0.0
    if push_time_total > 0:
        psi = (damage / (deaths + 1)) * (1.0 / math.sqrt(push_time_total + 1))

    league_push_time_per_season = league_averages.get("push_time_per_season", 1.0)
    push_time_norm = push_time_per_season / league_push_time_per_season if league_push_time_per_season > 0 else 0.0

    return {
        "push_time_total": push_time_total,
        "push_time_per_season": push_time_per_season,
        "push_time_norm": push_time_norm,
        "psi": psi,
    }


def compute_payload_objective_team_scores(team_player_entries):
    """
    team_player_entries: list of (player_id, player_entry_from_career_db)

    Returns dict {pid: obj_pl_score}
    """
    # PresencePL: share of team push time
    total_push_time = sum(p["objective_payload_components"]["push_time_total"]
                          for _, p in team_player_entries)
    if total_push_time <= 0:
        total_push_time = 1.0

    scores = {}
    for pid, pdata in team_player_entries:
        comp = pdata["objective_payload_components"]
        presence_pl = comp["push_time_total"] / total_push_time

        push_time_norm = comp["push_time_norm"]
        psi = comp["psi"]

        # Normalize PSI within team to avoid extreme outliers dominating
        # We'll compute team PSI mean and std first
        scores[pid] = {
            "presence_pl": presence_pl,
            "push_time_norm": push_time_norm,
            "psi": psi,
        }

    # PSI normalization within team
    psi_values = [v["psi"] for v in scores.values()]
    if psi_values:
        mean_psi = sum(psi_values) / len(psi_values)
        var_psi = sum((x - mean_psi) ** 2 for x in psi_values) / max(1, len(psi_values))
        std_psi = math.sqrt(var_psi)
    else:
        mean_psi = 0.0
        std_psi = 1.0

    for pid, v in scores.items():
        if std_psi > 0:
            psi_norm = (v["psi"] - mean_psi) / std_psi
        else:
            psi_norm = 0.0

        # Final ObjPL score (website‑only version)
        # 0.40 Presence + 0.40 PushTimeNorm + 0.20 PSI_norm
        obj_pl = (0.40 * v["presence_pl"]) + (0.40 * v["push_time_norm"]) + (0.20 * psi_norm)
        v["obj_pl"] = obj_pl

    return {pid: v["obj_pl"] for pid, v in scores.items()}