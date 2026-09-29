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
                # Never let last_season regress — protects against an
                # out-of-order or differently-scaled call (e.g. an older
                # rebuild) accidentally making a still-active player look
                # stale to any recency check elsewhere in the app.
                prev = entry.get("last_season")
                entry["last_season"] = season if prev is None else max(prev, season)
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

    # ---------------------------------------------------------
    # One-time cleanup: remove phantom canonical entries created by a
    # since-fixed bug where a canonical ID string (e.g. "player_519")
    # was mistakenly passed into resolve() as if it were a raw UUID,
    # minting a bogus new canonical entry with that string recorded as
    # its "uuid". These are always empty shells: no real names, no
    # team history, and their sole "uuid" looks like "player_N" rather
    # than a genuine UUID. Real UUIDs always contain hyphens and don't
    # start with "player_".
    # ---------------------------------------------------------
    def remove_phantom_entries(self, dry_run=True):
        removed = []
        for cid, entry in list(self.data["canonical"].items()):
            uuids = entry.get("uuids", [])
            is_phantom = (
                len(uuids) == 1
                and uuids[0].startswith("player_")
                and "-" not in uuids[0]
                and not entry.get("names")
                and not entry.get("team_history")
            )
            if is_phantom:
                removed.append(cid)
                if not dry_run:
                    del self.data["canonical"][cid]
                    self.data["uuid_to_canonical"].pop(uuids[0], None)

        if removed and not dry_run:
            self.save()
        return removed