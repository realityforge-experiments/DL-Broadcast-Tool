import os
import json

# Paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAREER_DB_PATH = os.path.join(PROJECT_ROOT, "career_stats.json")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")

ROOKIE_KILL_THRESHOLD = 1000


def load_career_db():
    if not os.path.exists(CAREER_DB_PATH):
        return None
    with open(CAREER_DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_current_teams():
    """
    The set of teams currently competing, per config.json — the same
    source of truth used for tiers. A team can be dissolved (e.g. EMU)
    without the app ever being told individual players left; this list
    is what actually reflects reality right now.
    """
    if not os.path.exists(CONFIG_PATH):
        return None
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    teams = config.get("teams")
    return set(teams) if teams else None


def get_rookies(db):
    """
    Rookie definition: career kills < 1000, full stop — regardless of how
    many seasons the player has been around, how many maps they've
    played, or whether they've played this specific season. A veteran
    who simply hasn't racked up kills yet is still a rookie by this
    definition; maps/KD are shown alongside for context only, they don't
    gate eligibility.

    Falls back to the TOP-LEVEL "kills" field (populated by on_sync_stats
    for anyone with live current-season activity) when "career" is
    missing entirely — e.g. a player who isn't in the local
    match_history.db cache that build_career_database depends on, which
    only covers past seasons. Without this fallback, an established
    veteran missing from that cache would incorrectly read as 0 kills
    and show up here as a "rookie".
    """
    rookies = {}
    for pid, p in db.get("players", {}).items():
        career = p.get("career")
        if career:
            kills = career.get("kills", 0) or 0
        else:
            kills = p.get("kills", 0) or 0
        if kills < ROOKIE_KILL_THRESHOLD:
            rookies[pid] = p
    return rookies


def rank_rookies_by_tag(season, tag_name, limit=15):
    db = load_career_db()
    if db is None:
        return []
    rookies = get_rookies(db)
    current_teams = load_current_teams()

    rows = []
    for pid, p in rookies.items():
        career = p.get("career") or {}

        # Pull core stats — fall back to top-level fields (populated by
        # on_sync_stats) when "career" is missing, same reasoning as
        # get_rookies() above.
        kills_val = career.get("kills", p.get("kills", 0))
        kd_val = career.get("KD", p.get("kd", 0))
        score_val = career.get("score", p.get("score", 0))
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

        # Free agents are excluded entirely — a player with no current
        # team could simply have left the league a while back, and would
        # otherwise sit stuck in this table forever with no way to ever
        # graduate out of it.
        if team_name == "Free Agent":
            continue

        # Also exclude anyone whose last known team has since been
        # dissolved (e.g. EMU) — team_history never gets updated when a
        # team folds, only when a player joins somewhere new, so without
        # this a departed/dissolved-team player stays stuck in the
        # rookie table forever just like a free agent would.
        if current_teams is not None and team_name not in current_teams:
            continue

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
