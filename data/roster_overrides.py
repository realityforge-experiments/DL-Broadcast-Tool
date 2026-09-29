import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROSTER_OVERRIDES_PATH = os.path.join(BASE_DIR, "roster_overrides.json")


def load_roster_overrides():
    """
    Returns {canonical_id: team_name} for players whose current team has
    been manually set — e.g. a mid-season merge/roster move where the
    player hasn't played a match under the new team yet, so the
    match-derived team_history hasn't caught up. This always takes
    priority over team_history when determining a player's current team.
    """
    if not os.path.exists(ROSTER_OVERRIDES_PATH):
        return {}
    with open(ROSTER_OVERRIDES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_roster_overrides(overrides):
    with open(ROSTER_OVERRIDES_PATH, "w", encoding="utf-8") as f:
        json.dump(overrides, f, indent=2)


def set_override(canonical_id, team_name):
    overrides = load_roster_overrides()
    overrides[canonical_id] = team_name
    save_roster_overrides(overrides)
    return overrides


def clear_override(canonical_id):
    overrides = load_roster_overrides()
    overrides.pop(canonical_id, None)
    save_roster_overrides(overrides)
    return overrides
