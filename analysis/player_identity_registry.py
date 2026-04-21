import json
import os

PIR_PATH = os.path.join(os.path.dirname(__file__), "player_identity_registry.json")

class PlayerIdentityRegistry:
    def __init__(self):
        if os.path.exists(PIR_PATH):
            with open(PIR_PATH, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {"uuid_to_canonical": {}, "canonical": {}}

    def save(self):
        with open(PIR_PATH, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def resolve(self, uuid):
        """Return canonical ID for a UUID, or create one."""
        uuid = str(uuid)
        if uuid in self.data["uuid_to_canonical"]:
            return self.data["uuid_to_canonical"][uuid]

        # Create new canonical ID
        canonical = f"player_{len(self.data['canonical'])+1}"
        self.data["uuid_to_canonical"][uuid] = canonical
        self.data["canonical"][canonical] = {"uuids": [uuid], "names": []}
        self.save()
        return canonical

    def add_name(self, canonical, name):
        entry = self.data["canonical"].setdefault(canonical, {"uuids": [], "names": []})
        if name not in entry["names"]:
            entry["names"].append(name)
            self.save()

    def merge(self, uuid_a, uuid_b):
        """Merge two UUIDs into one canonical identity."""
        ca = self.resolve(uuid_a)
        cb = self.resolve(uuid_b)
        if ca == cb:
            return ca

        # Merge cb into ca
        self.data["canonical"][ca]["uuids"].extend(self.data["canonical"][cb]["uuids"])
        self.data["canonical"][ca]["names"].extend(self.data["canonical"][cb]["names"])

        # Update uuid_to_canonical
        for u in self.data["canonical"][cb]["uuids"]:
            self.data["uuid_to_canonical"][u] = ca

        del self.data["canonical"][cb]
        self.save()
        return ca