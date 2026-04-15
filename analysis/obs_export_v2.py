import os

from analysis.player_summary_v2 import build_player_summary
from analysis.team_identity_v2 import format_team_identity, generate_team_identity_block
from analysis.storylines import generate_storyline
from analysis.predictions_v2 import generate_prediction

import re

def safe_filename(name):
    # Remove all illegal Windows filename characters
    return re.sub(r'[\\/:*?"<>|]', '', name)


def export_obs_player_summaries(output_folder, team_players):
    """
    Exports one OBS text file per player with their full summary.
    """

    os.makedirs(output_folder, exist_ok=True)

    for p in team_players:
        name = p.get("name", "Unknown")
        safe_name = safe_filename(name)

        path = os.path.join(output_folder, f"{safe_name}_summary.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(build_player_summary(p))


def export_obs_team_identity(output_folder, team_players, team_name):
    """
    Exports a team identity block for OBS.
    """

    os.makedirs(output_folder, exist_ok=True)

    safe_team = safe_filename(team_name)
    path = os.path.join(output_folder, f"{safe_team}_identity.txt")
    with open(path, "w", encoding="utf-8") as f:
        identity_data = generate_team_identity_block(team_players, team_name)
        identity_text = format_team_identity(identity_data)
        f.write(identity_text)


def export_obs_storyline(output_folder, teamA_players, teamB_players):
    """
    Exports the full storyline block for OBS.
    """

    os.makedirs(output_folder, exist_ok=True)

    path = os.path.join(output_folder, "match_storyline.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(generate_storyline(teamA_players, teamB_players))


def export_obs_prediction(output_folder, teamA_players, teamB_players, teamA_name, teamB_name):
    """
    Exports the match prediction block for OBS.
    """

    os.makedirs(output_folder, exist_ok=True)

    path = os.path.join(output_folder, "match_prediction.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(generate_prediction(teamA_players, teamB_players, teamA_name, teamB_name))


def export_all_obs(output_folder, teamA_players, teamB_players, teamA_name="TeamA", teamB_name="TeamB"):
    """
    Master export function for OBS.
    Generates:
        - Player summaries
        - Team identities
        - Match storyline
        - Match prediction
    """

    # Player summaries
    export_obs_player_summaries(os.path.join(output_folder, teamA_name), teamA_players)
    export_obs_player_summaries(os.path.join(output_folder, teamB_name), teamB_players)

    # Team identities
    export_obs_team_identity(output_folder, teamA_players, teamA_name)
    export_obs_team_identity(output_folder, teamB_players, teamB_name)

    # Storyline
    export_obs_storyline(output_folder, teamA_players, teamB_players)

    # Prediction
    export_obs_prediction(output_folder, teamA_players, teamB_players, teamA_name, teamB_name)