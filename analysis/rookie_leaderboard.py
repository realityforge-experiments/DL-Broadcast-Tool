import os
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAREER_DB_PATH = os.path.join(PROJECT_ROOT, "career_stats.json")


# ---------------------------------------------------------
# Load DB
# ---------------------------------------------------------

def load_career_db():
    if not os.path.exists(CAREER_DB_PATH):
        return None
    with open(CAREER_DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------
# Identify rookies
# ---------------------------------------------------------

def get_rookies(db, season):
    rookies = {}

    for pid, p in db.get("players", {}).items():
        seasons_played = p.get("seasons_played") or ""
        season_list = [int(s) for s in seasons_played.split(",") if s.isdigit()]

        # True rookie = only played this season
        if len(season_list) == 1 and season_list[0] == season:
            rookies[pid] = p

    return rookies


# ---------------------------------------------------------
# Rank rookies by a selected tag
# ---------------------------------------------------------

def rank_rookies_by_tag(season, tag_name, limit=10):
    """
    Rank rookies using REAL career stats.
    """

    db = load_career_db()
    if db is None:
        return []

    rookies = get_rookies(db, season)

    rows = []
    for pid, p in rookies.items():

        # Pull stats from career DB (correct source)
        kills = p.get("kills", 0)
        deaths = p.get("deaths", 0)
        score = p.get("score", 0)

        # KD
        if deaths > 0:
            kd = kills / deaths
        else:
            kd = kills

        # Raw score = KD (for now)
        raw = kd

        # Percentile placeholder (we can compute real percentiles later)
        pct = raw

        # Team
        team = "Unknown"
        if p.get("team_history"):
            team = p["team_history"][-1]

        rows.append({
            "id": pid,
            "name": p.get("name", "Unknown"),
            "team": team,
            "pct": pct,
            "tier": "C",   # placeholder until rookie tiers are added
            "raw": raw,
            "kd": kd,
            "kills": kills,
            "deaths": deaths,
            "score": score,
            "summary": "",
        })

    # Sort by raw score
    rows.sort(key=lambda x: x["raw"], reverse=True)

    # Assign ranks
    for i, r in enumerate(rows, start=1):
        r["rank"] = i

    return rows[:limit]