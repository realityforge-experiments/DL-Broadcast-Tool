import json
import os
from collections import Counter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAREER_DB_PATH = os.path.join(BASE_DIR, "career_stats.json")

def load_career_db():
    """Load career database with proper error handling."""
    if not os.path.exists(CAREER_DB_PATH):
        raise FileNotFoundError(f"Career database not found at: {CAREER_DB_PATH}\nPlease build it first.")
    
    try:
        with open(CAREER_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        raise ValueError("Career database is corrupted. Please rebuild it.")
    except Exception as e:
        raise RuntimeError(f"Failed to load career database: {e}")


def team_identity(team_name: str):
    """Generate team identity summary based on career tags."""
    db = load_career_db()
    players = db.get("players", {})

    # Find all players who have ever played for this team
    team_players = [
        p for p in players.values()
        if team_name in p.get("team_history", [])
    ]

    if not team_players:
        return {
            "team": team_name,
            "players": [],
            "tag_counts": {},
            "strengths": ["No players found with this team in history"],
            "weaknesses": []
        }

    # Count all identity tags across the team
    all_tags = [tag for p in team_players for tag in p.get("identity_tags", [])]
    tag_counts = Counter(all_tags)

    strengths = []
    weaknesses = []

    # --- Strengths ---
    if tag_counts.get("Slayer", 0) >= 2:
        strengths.append("High slayer firepower")
    if tag_counts.get("Objective Specialist", 0) >= 2:
        strengths.append("Strong objective control")
    if tag_counts.get("Anchor", 0) >= 1:
        strengths.append("Reliable anchor/backline")
    if tag_counts.get("Playmaker", 0) >= 1:
        strengths.append("Creative playmaking")
    if tag_counts.get("Consistent", 0) >= 2:
        strengths.append("Very consistent performers")

    # --- Weaknesses ---
    if tag_counts.get("Objective Specialist", 0) == 0:
        weaknesses.append("Lacking objective specialists")
    if tag_counts.get("Sharpshooter", 0) == 0:
        weaknesses.append("No dedicated sharpshooter")
    if tag_counts.get("Anchor", 0) == 0:
        weaknesses.append("Weak backline stability")
    if tag_counts.get("Veteran", 0) == 0 and tag_counts.get("Rookie", 0) >= 2:
        weaknesses.append("Very inexperienced roster")

    return {
        "team": team_name,
        "players": team_players,           # kept for potential future use
        "tag_counts": dict(tag_counts),
        "strengths": strengths or ["Balanced roster — no dominant strength"],
        "weaknesses": weaknesses or ["No major weaknesses identified"]
    }