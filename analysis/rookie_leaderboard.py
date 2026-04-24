import os
import json
import re

# Paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAREER_DB_PATH = os.path.join(PROJECT_ROOT, "career_stats.json")

def load_career_db():
    if not os.path.exists(CAREER_DB_PATH): return None
    with open(CAREER_DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def get_rookies(db, season):
    rookies = {}
    current_season_int = int(season)
    
    for pid, p in db.get("players", {}).items():
        career = p.get("career", {})
        maps_played = career.get("maps", 0)
        kills = career.get("kills", 0)
        
        # Determine if they are active this season
        matches = p.get("matches", [])
        played_this_season = any(int(m.get("CycleID", 0)) >= current_season_int for m in matches)
        
        # Registry check
        reg_first = p.get("first_season")
        
        # --- THE TRIPLE LOCK ---
        # 1. Must be active now
        # 2. Maps must be low (< 50)
        # 3. Kills must be low (< 800) - This catches veterans with missing history
        is_rookie = False
        if played_this_season and maps_played < 50 and kills < 1000:
            # Final check: Registry shouldn't show them in a previous season
            if reg_first is None or int(reg_first) >= current_season_int:
                is_rookie = True

        if is_rookie:
            rookies[pid] = p
    return rookies

# analysis/rookie_leaderboard.py

def rank_rookies_by_tag(season, tag_name, limit=15):
    db = load_career_db()
    if db is None: return []
    rookies = get_rookies(db, season)
    
    rows = []
    for pid, p in rookies.items():
        career = p.get("career", {})
        
        # Pull core stats
        kills_val = career.get("kills", 0)
        kd_val = career.get("KD", 0)
        score_val = career.get("score", 0)
        maps_val = career.get("maps", 0)
        
        # Team handling: use history, then registry, then Free Agent
        history = p.get("team_history", [])
        team_name = "Free Agent"
        
        # Search backward through history for a non-UUID name
        for t in reversed(history):
            if t and not (len(str(t)) > 20 and "-" in str(t)):
                team_name = str(t)
                break
        
        # If still Free Agent, check if the player object has a 'team' key 
        # (often populated during Sync)
        if team_name == "Free Agent" and p.get("team"):
            team_name = p.get("team")

        rows.append({
            "id": pid,
            "name": p.get("name", "Unknown"),
            "team": team_name,
            "tier": p.get(tag_name, {}).get("tier", "D"),
            "kd": kd_val,
            "kills": kills_val,
            "maps": maps_val,
            "score": score_val
        })

    # Sort by Score instead of Rating
    rows.sort(key=lambda x: x["score"], reverse=True)
    
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    return rows[:limit]