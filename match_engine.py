# match_engine.py

import os
import json
import math

from tags.objective_payload import compute_payload_objective_team_scores
from tags.objective_domination import (
    compute_dom_objective_for_match_player,
    compute_dom_objective_team_scores,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAREER_DB_PATH = os.path.join(BASE_DIR, "career_stats.json")


def load_career_db():
    if not os.path.exists(CAREER_DB_PATH):
        return None
    with open(CAREER_DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_player_entry(db, pid):
    return db["players"].get(str(pid)) or db["players"].get(pid)


def rank_match_players_slayer(match_players):
    """
    match_players: list of dicts from stats API (current season),
    each with at least: id, name, team
    Returns: list of ranked players with slayer info
    """
    db = load_career_db()
    if db is None:
        return []

    ranked = []
    for p in match_players:
        pid = p.get("id")
        entry = _get_player_entry(db, pid)
        if not entry:
            continue
        score = entry.get("slayer_score_raw", 0.0)
        if score <= 0:
            continue
        ranked.append({
            "id": pid,
            "name": entry["name"],
            "team": p.get("team", "Unknown"),
            "score_raw": score,
            "score_display": entry.get("slayer_score_display", f"{score:.2f}"),
        })

    ranked.sort(key=lambda x: x["score_raw"], reverse=True)
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    return ranked


def rank_match_players_objdom(match_players):
    """
    Rank players by Domination Objective Specialist score (match-based).
    Uses DOM_Captures and DOM_Counters from match player stats.
    """

    db = load_career_db()
    if db is None:
        return []

    team_entries = []
    for p in match_players:
        pid = (
            p.get("id")
            or p.get("PlayerUUID")
            or p.get("uuid")
        )
        if not pid:
            continue

        entry = _get_player_entry(db, pid)
        if not entry:
            continue

        team_entries.append((pid, entry, p))

    if not team_entries:
        return []

    obj_scores = compute_dom_objective_team_scores(team_entries)

    ranked = []
    for pid, entry, mp in team_entries:
        score = obj_scores.get(pid)
        if score is None:
            continue

        ranked.append({
            "id": pid,
            "name": entry["name"],
            "team": mp.get("team", "Unknown"),
            "score_raw": score,
            "score_display": f"{score:.2f}",
        })

    ranked.sort(key=lambda x: x["score_raw"], reverse=True)

    for i, r in enumerate(ranked, 1):
        r["rank"] = i

    return ranked


def rank_match_players_objpl(match_players):
    db = load_career_db()
    if db is None:
        return []

    team_entries = []
    for p in match_players:
        pid = (
            p.get("id")
            or p.get("PlayerUUID")
            or p.get("uuid")
        )
        if not pid:
            continue

        entry = _get_player_entry(db, pid)
        if not entry:
            continue

        # ObjPL is match-based; we still attach career entry for name/team history
        team_entries.append((pid, entry, p))

    if not team_entries:
        return []

    obj_scores = compute_payload_objective_team_scores(team_entries)

    ranked = []
    for pid, entry, mp in team_entries:
        score = obj_scores.get(pid)
        if score is None:
            continue

        ranked.append({
            "id": pid,
            "name": entry["name"],
            "team": mp.get("team", "Unknown"),
            "score_raw": score,
            "score_display": f"{score:.2f}",
        })

    ranked.sort(key=lambda x: x["score_raw"], reverse=True)

    for i, r in enumerate(ranked, 1):
        r["rank"] = i

    return ranked


def split_two_columns(ranked_players, team_a_name, team_b_name):
    """
    Keeps global rank 1–N, but splits into left/right columns by team.
    """
    left = []
    right = []
    for p in ranked_players:
        if p["team"] == team_a_name:
            left.append(p)
        elif p["team"] == team_b_name:
            right.append(p)
        else:
            pass
    return left, right


def compute_slayer_prediction(team_a_players, team_b_players):
    """
    team_a_players / team_b_players: lists of ranked player dicts with slayer_score_raw
    Returns dict with team averages and win chances.
    """
    A = [p["score_raw"] for p in team_a_players]
    B = [p["score_raw"] for p in team_b_players]

    teamA_avg = sum(A) / max(1, len(A))
    teamB_avg = sum(B) / max(1, len(B))

    if max(teamA_avg, teamB_avg) == 0:
        slayer_edge = 0
    else:
        slayer_edge = (teamB_avg - teamA_avg) / max(teamA_avg, teamB_avg)

    k = 1.1
    pB = 1 / (1 + math.exp(-k * slayer_edge))
    pA = 1 - pB

    return {
        "teamA_avg": teamA_avg,
        "teamB_avg": teamB_avg,
        "teamA_win": round(pA * 100),
        "teamB_win": round(pB * 100),
    }


def rank_match_players_sharpshooter(match_players):
    db = load_career_db()
    if db is None:
        return []

    ranked = []
    for p in match_players:
        pid = p.get("id")
        entry = _get_player_entry(db, pid)
        if not entry:
            continue

        sharp = entry.get("sharpshooter", {})
        score = sharp.get("score_raw", 0.0)
        if score <= 0:
            continue

        ranked.append({
            "id": pid,
            "name": entry["name"],
            "team": p.get("team", "Unknown"),
            "score_raw": score,
            "score_display": sharp.get("score_display", f"{score:.2f}"),
        })

    ranked.sort(key=lambda x: x["score_raw"], reverse=True)
    for i, r in enumerate(ranked, 1):
        r["rank"] = i

    return ranked


def rank_match_players_clutch(players):
    ranked = []
    for p in players:
        score = p.get("clutch_components", {}).get("clutch_norm", 0.0)
        ranked.append({
            "name": p.get("name", "Unknown"),
            "team": p.get("team", ""),
            "score_raw": score,
            "score_display": f"{score:.2f}",
        })

    ranked.sort(key=lambda x: x["score_raw"], reverse=True)

    for i, r in enumerate(ranked, start=1):
        r["rank"] = i

    return ranked