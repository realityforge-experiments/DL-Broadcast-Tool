# prediction_engine.py (Modernized)

import math
import os
import json

from analysis.team_identity_v2 import generate_team_identity_block

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAREER_DB_PATH = os.path.join(BASE_DIR, "final_db.json")


# ---------------------------------------------------------
# Load DB
# ---------------------------------------------------------

def load_career_db():
    if not os.path.exists(CAREER_DB_PATH):
        return None
    with open(CAREER_DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_player_entry(db, pid):
    pid = str(pid)
    return db["players"].get(pid)


# ---------------------------------------------------------
# Logistic Win Chance
# ---------------------------------------------------------

def logistic_win_chance(teamA_avg, teamB_avg, k=1.1):
    if max(teamA_avg, teamB_avg) == 0:
        return 50, 50

    edge = (teamB_avg - teamA_avg) / max(teamA_avg, teamB_avg)
    pB = 1 / (1 + math.exp(-k * edge))
    pA = 1 - pB

    return round(pA * 100), round(pB * 100)


# ---------------------------------------------------------
# Compute Tag Averages (Modern Tag System)
# ---------------------------------------------------------

def compute_tag_averages(teamA_players, teamB_players):
    """
    Compute team averages using modern tag raw scores.
    Each player dict must contain:
        - id
        - team
    """

    db = load_career_db()
    if db is None:
        return {}

    def avg_tag(players, tag_name):
        vals = []
        for p in players:
            pid = p.get("id") or p.get("PlayerUUID") or p.get("uuid")
            entry = _get_player_entry(db, pid)
            if not entry:
                continue
            tag = entry.get(tag_name, {})
            vals.append(tag.get("raw", 0.0))
        return sum(vals) / max(1, len(vals))

    return {
        "Slayer": (
            avg_tag(teamA_players, "slayer"),
            avg_tag(teamB_players, "slayer"),
        ),
        "ObjPL": (
            avg_tag(teamA_players, "objective_payload"),
            avg_tag(teamB_players, "objective_payload"),
        ),
        "ObjDOM": (
            avg_tag(teamA_players, "objective_domination"),
            avg_tag(teamB_players, "objective_domination"),
        ),
        "Sharpshooter": (
            avg_tag(teamA_players, "sharpshooter"),
            avg_tag(teamB_players, "sharpshooter"),
        ),
        "Consistency": (
            avg_tag(teamA_players, "consistency"),
            avg_tag(teamB_players, "consistency"),
        ),
        "Clutch": (
            avg_tag(teamA_players, "clutch"),
            avg_tag(teamB_players, "clutch"),
        ),
    }


# ---------------------------------------------------------
# Full Prediction Engine (Option D)
# ---------------------------------------------------------

def generate_predictions(teamA_players, teamB_players):
    team_a = teamA_players[0].get("team", "Team A")
    team_b = teamB_players[0].get("team", "Team B")

    # --- Compute averages ---
    avgs = compute_tag_averages(teamA_players, teamB_players)

    # --- Per-tag win chances ---
    per_tag = {}
    for tag, (a_avg, b_avg) in avgs.items():
        per_tag[tag] = logistic_win_chance(a_avg, b_avg)

    # --- Weighted overall prediction ---
    weights = {
        "Slayer": 0.30,
        "ObjPL": 0.25,
        "ObjDOM": 0.25,
        "Sharpshooter": 0.10,
        "Consistency": 0.05,
        "Clutch": 0.05,
    }

    overall_A = sum(per_tag[tag][0] * w for tag, w in weights.items())
    overall_B = sum(per_tag[tag][1] * w for tag, w in weights.items())

    total = overall_A + overall_B
    if total > 0:
        overall_A = round((overall_A / total) * 100)
        overall_B = 100 - overall_A
    else:
        overall_A = overall_B = 50

    # --- Narrative summary ---
    narrative = []

    def add_line(tag, a, b):
        if a > b:
            narrative.append(f"{team_a} hold the edge in {tag}.")
        elif b > a:
            narrative.append(f"{team_b} hold the edge in {tag}.")

    for tag, (a_avg, b_avg) in avgs.items():
        add_line(tag, a_avg, b_avg)

    if overall_A > overall_B:
        narrative.append(f"Overall, {team_a} enter this matchup with a slight advantage.")
    elif overall_B > overall_A:
        narrative.append(f"Overall, {team_b} enter this matchup with a slight advantage.")
    else:
        narrative.append("Overall, this matchup looks extremely close.")

    # --- Build final text output ---
    lines = []
    lines.append(f"MATCH PREDICTIONS — {team_a} vs {team_b}\n")

    for tag, (pA, pB) in per_tag.items():
        lines.append(f"{tag} Win Chance: {team_a} {pA}% — {team_b} {pB}%")

    lines.append("\nOVERALL WIN CHANCE:")
    lines.append(f"{team_a} {overall_A}% — {team_b} {overall_B}%")

    lines.append("\nNARRATIVE SUMMARY:")
    lines.append(" ".join(narrative))

    return "\n".join(lines)