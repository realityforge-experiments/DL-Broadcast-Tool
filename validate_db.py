import json
import os
from pprint import pprint

DB_PATH = "final_db.json"

def validate_tag(player, tag_name):
    tag = player.get(tag_name)
    if not tag:
        return f"[MISSING] {tag_name}"

    required = ["raw", "pct", "tier", "summary"]
    missing = [k for k in required if k not in tag]

    if missing:
        return f"[INVALID] {tag_name} missing fields: {missing}"

    return f"[OK] {tag_name}: raw={tag['raw']:.3f}, pct={tag['pct']:.1f}, tier={tag['tier']}"

def main():
    if not os.path.exists(DB_PATH):
        print("ERROR: final_db.json not found. Build the DB first.")
        return

    with open(DB_PATH, "r", encoding="utf-8") as f:
        db = json.load(f)

    players = db.get("players", {})
    if not players:
        print("ERROR: No players found in DB.")
        return

    print(f"Loaded {len(players)} players.")
    print()

    # Pick first 3 players for inspection
    sample_players = list(players.items())[:3]

    for pid, pdata in sample_players:
        print("=" * 60)
        print(f"PLAYER: {pdata.get('name', pid)}")
        print(f"UUID: {pid}")
        print("-" * 60)

        for tag in ["slayer", "sharpshooter", "objective_payload", "consistency", "clutch"]:
            print(validate_tag(pdata, tag))

        print()

        # Optional: print full tag block for manual inspection
        print("FULL TAG BLOCKS:")
        for tag in ["slayer", "sharpshooter", "objective_payload", "consistency", "clutch"]:
            print(f"\n--- {tag.upper()} ---")
            pprint(pdata.get(tag))

        print("\n")

    print("=" * 60)
    print("LEAGUE AVERAGES:")
    pprint(db.get("league_averages", {}))

    print("\nDone.")

if __name__ == "__main__":
    main()