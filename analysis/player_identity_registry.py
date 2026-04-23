import json
import os

PIR_PATH = os.path.join(os.path.dirname(__file__), "player_identity_registry.json")


class PlayerIdentityRegistry:
    def __init__(self):
        if os.path.exists(PIR_PATH):
            with open(PIR_PATH, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {
                "uuid_to_canonical": {},
                "canonical": {}
            }

    def save(self):
        with open(PIR_PATH, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    # ---------------------------------------------------------
    # Resolve UUID → canonical ID (and create if needed)
    # ---------------------------------------------------------
    def resolve(self, uuid, season=None):
        uuid = str(uuid)

        # Known UUID
        if uuid in self.data["uuid_to_canonical"]:
            cid = self.data["uuid_to_canonical"][uuid]
            entry = self.data["canonical"][cid]
            if season is not None:
                entry["last_season"] = season
            return cid

        # New UUID → new canonical ID
        cid = f"player_{len(self.data['canonical']) + 1}"
        self.data["uuid_to_canonical"][uuid] = cid
        self.data["canonical"][cid] = {
            "uuids": [uuid],
            "names": [],
            "team_history": [],
            "first_season": season,
            "last_season": season,
        }
        self.save()
        return cid

    # ---------------------------------------------------------
    # Track name changes
    # ---------------------------------------------------------
    def update_name(self, canonical_id, name):
        entry = self.data["canonical"].get(canonical_id)
        if not entry:
            return

        if name and name not in entry["names"]:
            entry["names"].append(name)
            self.save()

    # ---------------------------------------------------------
    # Track team history
    # ---------------------------------------------------------
    def update_team(self, canonical_id, team):
        entry = self.data["canonical"].get(canonical_id)
        if not entry:
            return

        if team and (not entry["team_history"] or entry["team_history"][-1] != team):
            entry["team_history"].append(team)
            self.save()
            
    # ---------------------------------------------------------
    # Backwards compatibility: old method name
    # ---------------------------------------------------------
    def add_name(self, canonical_id, name):
        """Legacy alias for update_name()."""
        self.update_name(canonical_id, name)

    def add_team(self, canonical_id, team):
        """Legacy alias for update_team()."""
        self.update_team(canonical_id, team)        
            
            

    # ---------------------------------------------------------
    # Rookie detection
    # ---------------------------------------------------------
    def get_first_season(self, canonical_id):
        entry = self.data["canonical"].get(canonical_id)
        if not entry:
            return None
        return entry.get("first_season")