import os
import json

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


# ---------------------------------------------------------
# Career Rankings (Modern Tag System)
# ---------------------------------------------------------

def top_players_by_tag(tag_name, limit=20):
    """
    Returns top players sorted by percentile for a given tag.
    tag_name must match the new tag keys:
        - slayer
        - sharpshooter
        - objective_payload
        - objective_domination
        - consistency
        - clutch
    """

    db = load_career_db()
    if db is None:
        return []

    players = db.get("players", {})

    ranked = []
    for pid, p in players.items():
        tag = p.get(tag_name, {})
        pct = tag.get("pct", 0)

        ranked.append({
            "id": pid,
            "name": p.get("name", "Unknown"),
            "team": p.get("team_history", ["Unknown"])[-1] if p.get("team_history") else "Unknown",
            "pct": pct,
            "tier": tag.get("tier", "D"),
            "summary": tag.get("summary", ""),
            "raw": tag.get("raw", 0.0),
        })

    ranked.sort(key=lambda x: x["pct"], reverse=True)
    return ranked[:limit]


# ---------------------------------------------------------
# Match-Based Consistency Ranking (Modernized)
# ---------------------------------------------------------

def rank_match_players_consistency(players):
    ranked = []

    for p in players:
        tag = p.get("consistency", {})
        raw = tag.get("raw", 0.0)
        pct = tag.get("pct", None)
        tier = tag.get("tier", None)

        ranked.append({
            "name": p.get("name", "Unknown"),
            "team": p.get("team", ""),
            "score_raw": raw,
            "score_display": f"{raw:.2f}",
            "pct": pct,
            "tier": tier,
        })

    ranked.sort(key=lambda x: x["score_raw"], reverse=True)

    for i, r in enumerate(ranked, start=1):
        r["rank"] = i

    return ranked


# ---------------------------------------------------------
# Match-Based Clutch Ranking (Modernized)
# ---------------------------------------------------------

def rank_match_players_clutch(players):
    ranked = []

    for p in players:
        tag = p.get("clutch", {})
        raw = tag.get("raw", 0.0)
        pct = tag.get("pct", None)
        tier = tag.get("tier", None)

        ranked.append({
            "name": p.get("name", "Unknown"),
            "team": p.get("team", ""),
            "score_raw": raw,
            "score_display": f"{raw:.2f}",
            "pct": pct,
            "tier": tier,
        })

    ranked.sort(key=lambda x: x["score_raw"], reverse=True)

    for i, r in enumerate(ranked, start=1):
        r["rank"] = i

    return ranked


# ---------------------------------------------------------
# Generic Match Tag Ranking (Modern Tag System)
# ---------------------------------------------------------

def rank_match_players_by_tag(players, tag):
    rows = []

    for p in players:
        tag_data = p.get(tag) or {}
        raw = tag_data.get("raw", 0.0)
        pct = tag_data.get("pct", None)
        tier = tag_data.get("tier", None)

        rows.append({
            "name": p.get("name", "Unknown"),
            "team": p.get("team", ""),
            "score_raw": raw,
            "score_display": f"{raw:.2f}",
            "pct": pct,
            "tier": tier,
            # Prefer the tag's OWN explicit has_data flag (set by
            # resolve_tag_career_first / the Consistency step in
            # on_generate_slots) — those dicts are always non-empty even
            # for a "no career data" fallback estimate, so bool(tag_data)
            # alone can't tell the two cases apart.
            "has_data": tag_data.get("has_data", bool(tag_data)),
        })

    rows.sort(key=lambda x: x["score_raw"], reverse=True)

    for i, r in enumerate(rows, start=1):
        r["rank"] = i

    return rows


# ---------------------------------------------------------
# Split into two columns for UI
# ---------------------------------------------------------

def split_two_columns(ranked, team_a, team_b):
    left = [r for r in ranked if r.get("team") == team_a]
    right = [r for r in ranked if r.get("team") == team_b]
    return left, right