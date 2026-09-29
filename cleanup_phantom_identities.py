"""
One-time cleanup: removes phantom canonical entries from
analysis/player_identity_registry.json that were created by the
now-fixed canonical-resolution bug (a canonical ID string like
"player_519" got fed into resolve() as if it were a raw UUID, minting
a bogus empty entry). Safe to run any time — it only touches entries
matching that exact signature (a single fake "player_N" uuid, no
names, no team history). Real players are never touched.

Run with:  python cleanup_phantom_identities.py
Add --apply to actually delete them; without it, this only reports
what WOULD be removed (dry run).
"""
import sys
from analysis.player_identity_registry import PlayerIdentityRegistry

apply_changes = "--apply" in sys.argv

pir = PlayerIdentityRegistry()
removed = pir.remove_phantom_entries(dry_run=not apply_changes)

if not removed:
    print("No phantom entries found. Nothing to clean up.")
elif apply_changes:
    print(f"Removed {len(removed)} phantom entries:")
    for cid in removed:
        print(" -", cid)
else:
    print(f"DRY RUN: would remove {len(removed)} phantom entries:")
    for cid in removed:
        print(" -", cid)
    print("\nRun again with --apply to actually delete them.")
