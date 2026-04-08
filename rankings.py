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
        # For rankings, we approximate team context by using league‑wide push components
        # and treat all players as if they were on one "virtual team".
        team_entries = [(pid, p) for pid, p in players.items()]
        obj_scores = compute_payload_objective_team_scores(team_entries)

        for pid, p in players.items():
            score = obj_scores.get(pid, 0.0)
            if score <= 0:
                continue
            results.append({
                "id": pid,
                "name": p["name"],
                "team": p["team_history"][-1] if p["team_history"] else "Unknown",
                "score_raw": score,
                "score_display": f"{score:.2f}",
            })

        results = [r for r in results if r["score_raw"] > 0]
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