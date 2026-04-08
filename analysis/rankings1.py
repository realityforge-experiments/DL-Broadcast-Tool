import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAREER_DB = os.path.join(BASE_DIR, "career_stats.json")

def load_db():
    with open(CAREER_DB, "r", encoding="utf-8") as f:
        return json.load(f)

def top_players_by_tag(tag, limit=10):
    db = load_db()
    players = db["players"]

    ranked = [
        p for p in players.values()
        if tag in p.get("identity_tags", [])
    ]

    # Sort by slayer_index for Slayers, objective_index for Objective Specialists, etc.
    def score(p):
        norm = p["normalized"]
        if tag == "Slayer":
            return norm["slayer_index"]
        if tag == "Objective Specialist":
            return norm["objective_index"]
        if tag == "Sharpshooter":
            return p["career"]["accuracy"]
        if tag == "Anchor":
            return norm["survivability_index"]
        if tag == "Aggressor":
            return norm["kills_per_map"]
        if tag == "Clutch":
            return norm["win_rate"]
        return p["career"]["KD"]

    ranked.sort(key=score, reverse=True)
    return ranked[:limit]