import json
from data.career_db import build_career_database

def test_career_db_consistency_output(tmp_path):
    out = tmp_path / "career_stats.json"
    ok = build_career_database(str(out))
    assert ok is True

    data = json.loads(out.read_text())
    players = data["players"]

    # Ensure at least one player has consistency data
    assert len(players) > 0

    sample = next(iter(players.values()))
    cons = sample.get("consistency", None)
    assert cons is not None

    # Check required fields
    assert "raw" in cons
    assert "pct" in cons
    assert "tier" in cons
    assert "summary" in cons
    assert "components" in cons
    assert "extras" in cons

    # Check component structure
    comps = cons["components"]
    assert "floor" in comps
    assert "stability" in comps
    assert "average" in comps