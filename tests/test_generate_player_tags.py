from dashleague_cast_tool import DashLeagueGUI

def test_generate_player_tags_consistency():
    gui = DashLeagueGUI.__new__(DashLeagueGUI)  # bypass Tk init

    player = {
        "slayer": {"strength": "S+"},
        "consistency": {"raw": 0.82},
        "objective_payload_components": {"payload_score_raw": 0.55},
        "objective_domination_components": {"raw": 0.44},
        "sharpshooter": {"score": 0.66},
    }

    tags = gui.generate_player_tags(player, map_type="Payload")
    assert "Cons 0.82" in tags
    assert "ObjPL 0.55" in tags
    assert "Sharp 0.66" in tags