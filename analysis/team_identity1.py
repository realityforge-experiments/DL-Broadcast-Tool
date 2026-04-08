import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAREER_DB = os.path.join(BASE_DIR, "career_stats.json")

def load_db():
    with open(CAREER_DB, "r", encoding="utf-8") as f:
        return json.load(f)

def team_identity(team_name):
    db = load_db()
    players = db["players"]

    team_players = [
        p for p in players.values()
        if team_name in p.get("team_history", [])
    ]

    tag_counts = {}
    for p in team_players:
        for tag in p.get("identity_tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    strengths = []
    weaknesses = []

    if tag_counts.get("Slayer", 0) >= 2:
        strengths.append("High slayer power")
    if tag_counts.get("Objective Specialist", 0) >= 2:
        strengths.append("Strong objective depth")
    if tag_counts.get("Anchor", 0) >= 1:
        strengths.append("Stable backline")

    if tag_counts.get("Objective Specialist", 0) == 0:
        weaknesses.append("Weak objective presence")
    if tag_counts.get("Sharpshooter", 0) == 0:
        weaknesses.append("No true sharpshooter")

    return {
        "team": team_name,
        "players": team_players,
        "tag_counts": tag_counts,
        "strengths": strengths,
        "weaknesses": weaknesses
    }