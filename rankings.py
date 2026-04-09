import os
import json

from tags.objective_payload import compute_payload_objective_team_scores

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAREER_DB_PATH = os.path.join(BASE_DIR, "career_stats.json")


def load_career_db():
    if not os.path.exists(CAREER_DB_PATH):
        return None
    with open(CAREER_DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def top_players_by_tag(tag_name):
    db = load_career_db()
    if db is None:
        return []

    players = db["players"]
    league = db["league_averages"]

    results = []

    if tag_name == "Slayer":
        for pid, p in players.items():
            score = p.get("slayer_score_raw", 0.0)
            if score <= 0:
                continue
            results.append({
                "id": pid,
                "name": p["name"],
                "team": p["team_history"][-1] if p["team_history"] else "Unknown",
                "score_raw": score,
                "score_display": p.get("slayer_score_display", f"{score:.2f}"),
            })
        results = [r for r in results if r["score_raw"] > 0]
        results.sort(key=lambda x: x["score_raw"], reverse=True)
        return results

    if tag_name == "Payload Objective Specialist":
        for pid, p in players.items():
            comp = p.get("objective_payload_components", {})
            score = comp.get("payload_score_raw", 0.0)
            if score <= 0:
                continue

            results.append({
                "id": pid,
                "name": p["name"],
                "team": p["team_history"][-1] if p["team_history"] else "Unknown",
                "score_raw": score,
                "score_display": comp.get("payload_score_display", f"{score:.2f}"),
            })

        results.sort(key=lambda x: x["score_raw"], reverse=True)
        return results

    return []
    
def rank_match_players_consistency(players):
    ranked = []

    for p in players:
        components = p.get("consistency_components", {})

        # Prefer normalized score if present, else raw consistency, else 0.0
        score = components.get("consistency_norm")
        if score is None:
            score = components.get("consistency", 0.0)

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
    
def rank_match_players_clutch(players):
    ranked = []
    for p in players:
        score = p.get("clutch_components", {}).get("clutch_norm", 0.0)
        ranked.append({
            "name": p.get("name", "Unknown"),
            "team": p.get("team", ""),
            "score_raw": score,
            "score_display": f"{score:.2f}"
        })

    ranked.sort(key=lambda x: x["score_raw"], reverse=True)

    for i, r in enumerate(ranked, start=1):
        r["rank"] = i

    return ranked
    
    
def rank_match_players_objpl(players):
    """
    Rank players by match-based Payload Objective Specialist score.
    Uses match stats only (PAY_PushTime, damage, deaths).
    """

    db = load_career_db()
    if db is None:
        return []

    team_entries = []
    for p in players:
        pid = (
            p.get("id")
            or p.get("PlayerUUID")
            or p.get("uuid")
        )
        if not pid:
            continue

        career_entry = db["players"].get(pid, {})

        # Normalize match keys
        push = p.get("PAY_PushTime", 0) or 0
        dmg = p.get("damage", p.get("Damage", 0)) or 0
        deaths = p.get("deaths", p.get("Deaths", 0)) or 0

        # Only include players with actual payload participation
        if push <= 0:
            continue

        # Attach normalized values back to match player
        p["PAY_PushTime"] = push
        p["damage"] = dmg
        p["deaths"] = deaths

        team_entries.append((pid, career_entry, p))

    if not team_entries:
        return []

    # Compute match-based ObjPL
    obj_scores = compute_payload_objective_team_scores(team_entries)

    ranked = []
    for pid, entry, mp in team_entries:
        score = obj_scores.get(pid, 0.0)

        ranked.append({
            "id": pid,
            "name": entry.get("name", mp.get("name", "Unknown")),
            "team": mp.get("team", "Unknown"),
            "score_raw": score,
            "score_display": f"{score:.2f}",
        })

    ranked.sort(key=lambda x: x["score_raw"], reverse=True)

    for i, r in enumerate(ranked, 1):
        r["rank"] = i

    return ranked