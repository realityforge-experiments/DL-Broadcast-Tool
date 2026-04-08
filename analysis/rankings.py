import json
import os
from typing import List, Dict, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAREER_DB_PATH = os.path.join(BASE_DIR, "career_stats.json")


def load_career_db() -> Dict:
    """Load career database with proper error handling."""
    if not os.path.exists(CAREER_DB_PATH):
        raise FileNotFoundError(f"Career database not found at: {CAREER_DB_PATH}\nPlease build it first from the GUI.")

    try:
        with open(CAREER_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        raise ValueError("Career database is corrupted. Please rebuild it.")
    except Exception as e:
        raise RuntimeError(f"Failed to load career database: {e}")


def top_players_by_tag(
    tag: str, 
    players_only: List[Dict] = None, 
    career_db: Dict = None,
    limit: int = 10
) -> List[Dict]:
    """
    Return top players for a given identity tag.
    
    If players_only is provided → only rank within current match lineup (recommended for GUI).
    Otherwise → rank across entire career database.
    """
    if players_only is not None:
        # Use only the current match players (live stats)
        players = players_only[:]
    else:
        # Full career database
        db = career_db or load_career_db()
        players = list(db["players"].values())

    if not players:
        return []

    # Filter players who have this tag
    tagged_players = [
        p for p in players 
        if tag in p.get("identity_tags", [])
    ]

    if not tagged_players:
        return []

    # Define scoring function based on tag
    def get_score(p: Dict) -> float:
        norm = p.get("normalized", {})
        career = p.get("career", {})

        if tag == "Slayer":
            return norm.get("slayer_index", 0)
        elif tag == "Objective Specialist":
            return norm.get("objective_index", 0)
        elif tag == "Sharpshooter":
            return career.get("accuracy", 0)
        elif tag == "Anchor":
            return norm.get("survivability_index", 0)
        elif tag == "Aggressor":
            return norm.get("kills_per_map", 0)
        elif tag == "Clutch":
            return norm.get("win_rate", 0)
        elif tag == "Consistent":
            # Could add variance logic if stored
            return norm.get("kills_per_map", 0)
        else:
            # Default fallback
            return career.get("KD", 0)

    # Sort by score descending
    tagged_players.sort(key=get_score, reverse=True)

    return tagged_players[:limit]