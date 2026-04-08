import requests

BASE = "https://dashleague.games/api/v1"

def fetch_player_match_history(player_id):
    """
    Builds full match history for a player by iterating all seasons and matches.
    Returns a list of per-match stat dicts.
    """

    # 1. Fetch all seasons
    seasons_resp = requests.get(f"{BASE}/seasons")
    seasons = seasons_resp.json()

    history = []

    for season in seasons:
        sid = season.get("id")
        if not sid:
            continue

        # 2. Fetch all matches in this season
        matches_resp = requests.get(f"{BASE}/seasons/{sid}/matches")
        matches = matches_resp.json()

        for match in matches:
            mid = match.get("id")
            if not mid:
                continue

            # 3. Fetch full match details
            detail_resp = requests.get(f"{BASE}/match/{mid}")
            detail = detail_resp.json()

            mode = detail.get("mode", "").lower()

            # 4. Find player in match
            for p in detail.get("players", []):
                if p.get("id") == player_id:

                    entry = {
                        "kills": p.get("kills", 0),
                        "deaths": p.get("deaths", 0),
                        "accuracy": p.get("accuracy", 0.0),
                        "damage": p.get("damage", 0),
                        "push_time": p.get("PAY_PushTime", 0),
                        "captures": p.get("DOM_captures", 0),
                        "counters": p.get("DOM_counters", 0),
                        "mode": mode
                    }

                    history.append(entry)

    return history