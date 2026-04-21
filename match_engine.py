# match_engine.py (Modernized & GUI-Compatible)

import os
import json
import math

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAREER_DB_PATH = os.path.join(BASE_DIR, "final_db.json")


# ---------------------------------------------------------
# Load DB
# ---------------------------------------------------------

def load_career_db():
    if not os.path.exists(CAREER_DB_PATH):
        return None
    with open(CAREER_DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_player_entry(db, pid):
    pid = str(pid)
    return db["players"].get(pid)
    

def attach_career_tags_to_match_player(match_player, career_entry):
    """
    Injects career tag blocks into a match_player object so that
    storylines, predictions, and UI panels can access:
        - consistency
        - anchor
        - clutch
        - breaker
    """
    for tag in ("consistency", "anchor", "clutch", "breaker"):
        if tag in career_entry:
            match_player[tag] = career_entry[tag]


# ---------------------------------------------------------
# Universal Match Ranking (Career Tags)
# ---------------------------------------------------------

def rank_match_players_by_tag(match_players, tag_name):
    """
    Rank match players using career tag percentiles.
    """

    db = load_career_db()
    if db is None:
        return []

    ranked = []

    for p in match_players:
        pid = p.get("id") or p.get("PlayerUUID") or p.get("uuid")
        if not pid:
            continue

        entry = _get_player_entry(db, pid)
        if not entry:
            continue
            
        attach_career_tags_to_match_player(p, entry)    

        tag = entry.get(tag_name, {})
        pct = tag.get("pct", 0)
        raw = tag.get("raw", 0.0)

        ranked.append({
            "id": pid,
            "name": entry.get("name", "Unknown"),
            "team": p.get("team", "Unknown"),
            "pct": pct,
            "raw": raw,
            "tier": tag.get("tier", "D"),
            "summary": tag.get("summary", ""),
        })

    ranked.sort(key=lambda x: x["pct"], reverse=True)

    for i, r in enumerate(ranked, 1):
        r["rank"] = i

    return ranked


# ---------------------------------------------------------
# Match-Based Consistency (using match stats only)
# ---------------------------------------------------------

def rank_match_players_consistency(match_players):
    ranked = []

    for p in match_players:
        tag = p.get("consistency", {})
        raw = tag.get("raw", 0.0)

        ranked.append({
            "name": p.get("name", "Unknown"),
            "team": p.get("team", ""),
            "score_raw": raw,
            "score_display": f"{raw:.2f}",
        })

    ranked.sort(key=lambda x: x["score_raw"], reverse=True)

    for i, r in enumerate(ranked, 1):
        r["rank"] = i

    return ranked


# ---------------------------------------------------------
# Match-Based Clutch (using match stats only)
# ---------------------------------------------------------

def rank_match_players_clutch(match_players):
    ranked = []

    for p in match_players:
        tag = p.get("clutch", {})
        raw = tag.get("raw", 0.0)

        ranked.append({
            "name": p.get("name", "Unknown"),
            "team": p.get("team", ""),
            "score_raw": raw,
            "score_display": f"{raw:.2f}",
        })

    ranked.sort(key=lambda x: x["score_raw"], reverse=True)

    for i, r in enumerate(ranked, 1):
        r["rank"] = i

    return ranked


# ---------------------------------------------------------
# Utility: Split into two columns by team
# ---------------------------------------------------------

def split_two_columns(ranked_players, team_a_name, team_b_name):
    left = []
    right = []
    for p in ranked_players:
        if p["team"] == team_a_name:
            left.append(p)
        elif p["team"] == team_b_name:
            right.append(p)
    return left, right


# ---------------------------------------------------------
# Legacy-Compatible Wrappers (GUI expects these)
# ---------------------------------------------------------

def _add_score_fields(ranked):
    """Adds BOTH score_raw and score_display required by GUI."""
    for r in ranked:
        r["score_raw"] = r["raw"]
        r["score_display"] = f"{r['raw']:.2f}"
    return ranked


def rank_match_players_slayer(match_players):
    return _add_score_fields(rank_match_players_by_tag(match_players, "slayer"))


def rank_match_players_sharpshooter(match_players):
    return _add_score_fields(rank_match_players_by_tag(match_players, "sharpshooter"))


def rank_match_players_objpl(match_players):
    return _add_score_fields(rank_match_players_by_tag(match_players, "objective_payload"))


def rank_match_players_objdom(match_players):
    ranked = []

    for p in match_players:
        comp = p.get("objective_domination_components", {})
        raw = comp.get("raw", 0.0)

        ranked.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "team": p.get("team"),
            "score_raw": raw,
            "score_display": f"{raw:.2f}",
        })

    ranked.sort(key=lambda x: x["score_raw"], reverse=True)

    for i, r in enumerate(ranked, 1):
        r["rank"] = i

    return ranked
    
    
def rank_match_players_consistency_career(match_players):
    """
    Wraps rank_match_players_by_tag('consistency') so the output matches
    the expected structure for the rankings UI.
    """
    ranked = rank_match_players_by_tag(match_players, "consistency")
    out = []
    for i, p in enumerate(ranked, 1):
        out.append({
            "rank": i,
            "name": p["name"],
            "team": p.get("team", "Unknown"),
            "score_raw": p["raw"],
            "score_display": f"{p['raw']:.2f}",
        })
    return out

# ---------------------------------------------------------
# Legacy Slayer Prediction Wrapper
# ---------------------------------------------------------

def compute_slayer_prediction(team_a_players, team_b_players):
    """
    Legacy wrapper for GUI compatibility.
    Uses modern slayer.raw values instead of legacy slayer_score_raw.
    """

    A = [p.get("slayer", {}).get("raw", 0.0) for p in team_a_players]
    B = [p.get("slayer", {}).get("raw", 0.0) for p in team_b_players]

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
    
    