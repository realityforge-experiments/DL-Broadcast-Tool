import os
import json
import math
import threading
import functools
from http.server import HTTPServer, SimpleHTTPRequestHandler
from collections import defaultdict

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import requests

# ---------------------------------------------------------
# Internal modules — clean, correct, no duplicates
# ---------------------------------------------------------

# Career DB builder
from data.career_db import build_career_database

# Career rankings (used for global leaderboards)
from rankings import (
    top_players_by_tag,
    split_two_columns,
    rank_match_players_by_tag,
)

# Team identity + storyline + predictions
from analysis.team_identity_v2 import generate_team_identity_block
from analysis.storylines import generate_storyline, matchup_storyline, matchup_narrative
from analysis.predictions_v2 import generate_prediction
from analysis.rookie_leaderboard import rank_rookies_by_tag


# OBS export
from analysis.obs_export_v2 import export_all_obs

# Domination objective (match + career)
from tags.objective_domination import (
    compute_dom_objective_for_career_player,
    compute_dom_objective_for_match_player,
    compute_dom_objective_team_scores,
)

# Prediction engine (legacy but still used)
from predictions.prediction_engine import generate_predictions

# Match-based tag engines
from match_engine import (
    rank_match_players_slayer,
    rank_match_players_objpl,
    rank_match_players_objdom,
    rank_match_players_sharpshooter,
    rank_match_players_clutch,
    compute_slayer_prediction,
    rank_match_players_consistency_career,
    load_career_db, 
    attach_career_tags_to_match_player,
)

from data.tag_framework import percentile_rank, tier_from_percentile
from data.roster_overrides import load_roster_overrides, save_roster_overrides, set_override, clear_override

# ---------------------------------------------------------
#  PATHS + CONFIG
# ---------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
SCREENS_DIR = os.path.join(BASE_DIR, "screens")  



# Load config (or default)
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
else:
    config = {}

# Default output folder (outside repo)
DEFAULT_OUTPUT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", "stats"))

# Allow override from config.json
output_root = config.get("output_root", DEFAULT_OUTPUT_ROOT)

# Build runtime directories
STATS_DIR = output_root
PLAYERS_DIR = os.path.join(STATS_DIR, "players")
OBS_EXPORT_DIR = os.path.join(STATS_DIR, "obs_exports")

os.makedirs(PLAYERS_DIR, exist_ok=True)
os.makedirs(OBS_EXPORT_DIR, exist_ok=True)

API_BASE = "https://dashleague.games/api/v1"
LOCAL_OBS_SERVER_PORT = 8787


def export_to_obs(filename, text):
    path = os.path.join(OBS_EXPORT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path
    
    
# ---------------------------------------------------------
# Breaker (match-based)
# ---------------------------------------------------------

def compute_breaker_for_match_player(p):
    kills = p.get("kills", 0) or 0
    damage = p.get("damage", 0) or 0
    dom_counters = p.get("DOM_Counters", 0) or 0
    dom_caps = p.get("DOM_Captures", 0) or 0
    cp_caps = p.get("CP_Captures", 0) or 0

    raw = (
        dom_counters * 1.0 +
        dom_caps * 0.6 +
        cp_caps * 0.4 +
        kills * 0.05 +
        damage / 20000.0
    )

    return max(raw, 0.0)


# ---------------------------------------------------------
# Live-sync fallback formulas for every other tag. These are ONLY used
# when a player has no career data at all (e.g. missing from the local
# match_history.db cache that build_career_database depends on, which
# doesn't get refreshed with current-season activity). They REUSE the
# exact same real tag formulas career players get (tags/slayer.py,
# tags/sharpshooter.py, tags/anchor.py, tags/clutch.py,
# tags/breaker.py) fed with this season's live-synced cumulative stats,
# normalized against the SAME league averages — so the result is on a
# genuinely comparable scale to career-based scores, not a separate,
# incompatible calculation. Still always percentile-ranked only against
# OTHER no-data players in the same match, never mixed into a team
# average alongside real career-quality numbers, and always clearly
# labeled as an estimate wherever it's displayed.
# ---------------------------------------------------------

def estimate_maps_played(p, league_averages, career_db=None):
    """
    Prefers a VERIFIED current-season maps count when available (fetched
    per-player from /api/v1/player?PlayerID=X, which returns a real
    per-season breakdown — see step 4.5 in on_generate_slots). That
    value is already season-scoped, so it's used directly with no
    further adjustment.

    Otherwise, falls back to the bulk /stats endpoint's "maps" field,
    which is CAREER-TOTAL (lifetime maps ever played) despite being
    fetched from a season-filtered URL — confirmed against the
    website's own per-season breakdown. In that case, subtract whatever
    maps career_stats.json already has on file for this player (built
    from match_history.db, which only covers PAST seasons) to estimate
    just the current season's portion. For a player with no
    career_stats.json entry at all, there's nothing to subtract — the
    live total is used as-is, correct for a first-season player and an
    overestimate for anyone with unbuilt history we have no way to
    detect from here.

    Falls back further to a deaths-based estimate only if no maps figure
    is available at all.
    """
    if p.get("_verified_season_stats"):
        return max(1.0, float(p.get("maps") or 1))

    real_maps = p.get("maps")
    if real_maps:
        prior_maps = 0
        cid = p.get("canonical")
        if career_db and cid:
            pdata = career_db.get("players", {}).get(cid)
            if pdata:
                prior_maps = (pdata.get("career") or {}).get("maps", 0) or 0
        current_season_maps = float(real_maps) - float(prior_maps)
        return max(1.0, current_season_maps)

    deaths = p.get("deaths", 0) or 0
    avg_deaths_per_map = league_averages.get("deaths_per_map") or league_averages.get("deaths") or 1
    if avg_deaths_per_map <= 0:
        avg_deaths_per_map = 1
    return max(1.0, deaths / avg_deaths_per_map)


def _pseudo_career_dict(p, maps):
    return {
        "kills": p.get("kills", 0) or 0,
        "deaths": p.get("deaths", 0) or 0,
        "damage": p.get("damage", 0) or 0,
        "shots": p.get("shots", 0) or 0,
        "shots_hit": p.get("shots_hit", 0) or 0,
        "headshots": p.get("headshots", 0) or 0,
        "maps": maps,
    }


def compute_fallback_slayer(p, league_averages):
    from tags.slayer import compute_slayer_raw
    maps = estimate_maps_played(p, league_averages)
    pseudo = {"career": _pseudo_career_dict(p, maps)}
    return compute_slayer_raw(pseudo, league_averages)


def compute_fallback_sharpshooter(p, league_averages):
    from tags.sharpshooter import compute_sharpshooter_raw
    maps = estimate_maps_played(p, league_averages)
    career = _pseudo_career_dict(p, maps)
    return compute_sharpshooter_raw(career, league_averages)


def compute_fallback_anchor(p, league_averages):
    from tags.anchor import compute_anchor_raw
    maps = estimate_maps_played(p, league_averages)
    pseudo = {"career": _pseudo_career_dict(p, maps)}
    # Consistency genuinely can't be measured without per-match variance
    # data, so use the neutral midpoint here too — same treatment as
    # the standalone Consistency tag for no-data players.
    return compute_anchor_raw(pseudo, league_averages, 0.5)


def compute_fallback_clutch(p, league_averages):
    from tags.clutch import compute_clutch_raw
    maps = estimate_maps_played(p, league_averages)
    pseudo = {
        "career": _pseudo_career_dict(p, maps),
        "consistency_raw": 0.5,
    }
    return compute_clutch_raw(pseudo, league_averages)


def compute_fallback_payload(p, league_averages):
    # compute_payload_raw() needs real per-match granularity (a list of
    # individual matches) we don't have from live-sync cumulative
    # totals, so it can't be reused directly. Approximate on a
    # comparable scale instead: average push time per (estimated) map,
    # capped at the same 300s soft cap the real formula uses.
    maps = estimate_maps_played(p, league_averages)
    push = p.get("PAY_PushTime", 0) or 0
    avg_push = push / maps
    return min(avg_push / 300.0, 1.0)


def compute_breaker_for_match_player(p, league_averages):
    from tags.breaker import compute_breaker_raw
    maps = estimate_maps_played(p, league_averages)
    dmg_per_map = (p.get("damage", 0) or 0) / maps
    kills_per_map = (p.get("kills", 0) or 0) / maps
    return compute_breaker_raw(dmg_per_map, kills_per_map)


def compute_fallback_domination(p, league_averages):
    """
    Reuses the EXACT same log-scaled, PER-MAP formula
    compute_dom_objective_for_career_player uses, fed with this
    season's captures/counters divided by (estimated) maps played.
    """
    maps = estimate_maps_played(p, league_averages)
    caps = p.get("DOM_Captures", 0) or p.get("DOM_captures", 0) or 0
    counters = p.get("DOM_Counters", 0) or p.get("DOM_counters", 0) or 0
    caps_per_map = caps / maps
    counters_per_map = counters / maps
    league_avg_dom = (league_averages or {}).get("dom_actions", 1) or 1
    ceiling = max(1.0, league_avg_dom * 3)
    cap_rate = math.log1p(caps_per_map) / math.log1p(1 + ceiling)
    counter_rate = math.log1p(counters_per_map) / math.log1p(1 + ceiling)
    raw = (0.40 * cap_rate) + (0.60 * counter_rate)
    return max(0.05, min(raw, 1.0))


FALLBACK_FORMULAS = {
    "breaker": (compute_breaker_for_match_player, "Breaker"),
    "slayer": (compute_fallback_slayer, "Slayer"),
    "sharpshooter": (compute_fallback_sharpshooter, "Sharpshooter"),
    "objective_payload": (compute_fallback_payload, "Payload"),
    "objective_domination": (compute_fallback_domination, "Domination"),
    "anchor": (compute_fallback_anchor, "Anchor"),
    "clutch": (compute_fallback_clutch, "Clutch"),
}
    
    
# ---------------------------------------------------------
# Team Identity Formatter (Standalone Helper)
# ---------------------------------------------------------

def format_team_identity(identity):
    """
    Converts the identity block dict into readable caster-friendly text.
    """
    lines = []

    lines.append(f"Team Style: {identity.get('team_style', 'Unknown')}")
    lines.append("")

    lines.append("Strengths:")
    for s in identity.get("strengths", []):
        lines.append(f"  - {s}")

    lines.append("")

    lines.append("Weaknesses:")
    for w in identity.get("weaknesses", []):
        lines.append(f"  - {w}")

    lines.append("")

    lines.append("Tag Breakdown:")
    for tag, data in identity.get("tags", {}).items():
        lines.append(
            f"  - {tag.replace('_', ' ').title()}: "
            f"{data['tier']} Tier (avg {data['avg_pct']:.1f} percentile)"
        )

    return "\n".join(lines)    
    

def fetch_json(url):
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_player_season_stats(raw_uuid, season):
    """
    Calls /api/v1/player?PlayerID=X&playoffs=false to get EXACT
    per-season stats (maps, kills, deaths, damage, shots, shots_hit,
    headshots, CP_captures, PAY_PushTime, DOM_captures, DOM_counters)
    for one specific player. Far more accurate than the bulk /stats
    endpoint's "maps" field, which is career-cumulative despite being
    fetched from a season-filtered URL — confirmed against the
    website's own per-season breakdown. Only called for players
    missing from career_stats.json, so this is one extra request per
    player who actually needs it, not per sync.
    Returns None on any failure so callers can gracefully fall back to
    the cruder estimate instead.
    """
    try:
        url = f"{API_BASE}/player?PlayerID={raw_uuid}&playoffs=false"
        data = fetch_json(url)
        return (data.get("seasons") or {}).get(str(season))
    except Exception as e:
        print(f"Player season stats fetch failed for {raw_uuid}: {e}")
        return None


def ensure_player_slots():
    os.makedirs(PLAYERS_DIR, exist_ok=True)
    for i in range(10):
        slot_dir = os.path.join(PLAYERS_DIR, f"p{i}")
        os.makedirs(slot_dir, exist_ok=True)


def write_text(path, value):
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(value))


# ---------------------------------------------------------
# Roster / mid-season team tracking
# ---------------------------------------------------------

def get_current_team(cid, pir, overrides):
    """
    Returns a player's CURRENT team, honoring a manual roster override
    first (for mid-season moves/merges that haven't shown up in a synced
    match yet), falling back to the most recent entry in their
    match-derived team_history otherwise.
    """
    if cid in overrides:
        return overrides[cid]
    entry = pir.data.get("canonical", {}).get(cid, {})
    team_history = entry.get("team_history") or []
    return team_history[-1] if team_history else None


CAREER_AVERAGE_FIELDS = (
    "kills", "deaths", "score", "KD", "accuracy", "push_time",
    "DOM_Captures", "DOM_Counters", "maps", "damage", "shots",
    "shots_hit", "headshots",
)


def compute_team_average_career(career_db, team_canonical_ids):
    """
    Averages the 'career' block across the OTHER players on this specific
    team selection who already have real career data — NOT a league-wide
    average, and NOT tier-aware (Dasher/Sprinter/Walker), since a new
    player's own tier is unknown until they've played. This is used
    ONLY as a temporary display value inside the three team-comparison
    graphics (Tale of the Tape, Team DNA, Win Probability) so those
    graphics have something reasonable to plot for a new teammate. It is
    never written back to career_stats.json and never shown on a
    player's personal Spotlight card — a new player's individual stats
    stay untouched (empty) until they actually have real data.
    """
    players_db = career_db.get("players", {})
    totals = {field: 0.0 for field in CAREER_AVERAGE_FIELDS}
    count = 0

    for cid in team_canonical_ids:
        pdata = players_db.get(cid)
        if not pdata:
            continue
        career = pdata.get("career")
        if not career:
            continue
        count += 1
        for field in CAREER_AVERAGE_FIELDS:
            totals[field] += career.get(field, 0) or 0

    if count == 0:
        return {field: 0 for field in CAREER_AVERAGE_FIELDS}

    return {field: totals[field] / count for field in CAREER_AVERAGE_FIELDS}


def resolve_tag_career_first(all_players, tag_name, career_db, fallback_fn, label):
    """
    Generalizes the pattern originally built just for Breaker: use real
    career_stats.json data when a player has it, and ONLY fall back to a
    rough live-sync estimate for players who genuinely have none (e.g.
    missing from the local match_history.db cache build_career_database
    depends on — that cache only covers past seasons and never picks up
    current-season activity). Fallback players are explicitly marked
    has_data=False so they're excluded from team averages/predictions
    elsewhere, rather than silently counted as if they'd earned a real
    score of zero.
    """
    league_averages = (career_db or {}).get("league_averages", {})

    needs_fallback = []
    for p in all_players:
        cid = p.get("canonical")
        pdata = career_db["players"].get(cid) if (career_db and cid) else None
        career_tag = pdata.get(tag_name) if pdata else None
        if career_tag and career_tag.get("raw") is not None:
            p[tag_name] = dict(career_tag)
            p[tag_name]["has_data"] = True
        else:
            needs_fallback.append(p)

    if needs_fallback:
        for p in needs_fallback:
            p[tag_name] = {"raw": fallback_fn(p, league_averages)}

        # Percentile-rank against the REAL league-wide distribution
        # (saved by build_career_database) whenever it's available, so
        # these players are measured against the SAME population career
        # players are — not just each other. Ranking only against the
        # handful of other no-data players in this one match was
        # producing misleading results: a higher raw score could show a
        # LOWER percentile than a lower raw score from a different
        # player, simply because they were being compared against two
        # completely different populations (tiny match-local group vs.
        # the whole league).
        league_distribution = (career_db or {}).get("distributions", {}).get(tag_name)
        distribution = league_distribution if league_distribution else [p[tag_name]["raw"] for p in needs_fallback]

        for p in needs_fallback:
            raw = p[tag_name]["raw"]
            pct = percentile_rank(raw, distribution)
            tier = tier_from_percentile(pct)
            p[tag_name]["pct"] = pct
            p[tag_name]["tier"] = tier
            if p.get("_verified_season_stats"):
                # Real, verified current-season data (fetched per-player
                # from the API, not a guess) — no reason to exclude it
                # from team averages or flag it as an estimate anymore.
                p[tag_name]["has_data"] = True
                p[tag_name]["summary"] = (
                    f"{label}: {tier} Tier ({pct:.1f} percentile) — from verified "
                    f"current-season data (no prior-season career history on file yet)."
                )
            else:
                p[tag_name]["has_data"] = False
                p[tag_name]["summary"] = (
                    f"{label} ESTIMATE from this season's activity only — no "
                    f"career data on file yet. Not directly comparable to "
                    f"other players' career-based scores."
                )


def rename_player(cid, new_name):
    """
    Records a new current display name for a canonical player. Updates
    BOTH the identity registry (which keeps the full name history, used
    for team-roster display) AND career_stats.json's stored name (which
    is what the Spotlight card, Tale of the Tape, Team DNA, and Win
    Probability graphics all read) — otherwise a rename only shows up in
    half the app, which is exactly the bug this fixes.
    """
    from analysis.player_identity_registry import PlayerIdentityRegistry
    pir = PlayerIdentityRegistry()
    pir.update_name(cid, new_name)

    career_path = os.path.join(BASE_DIR, "career_stats.json")
    if os.path.exists(career_path):
        with open(career_path, "r", encoding="utf-8") as f:
            db = json.load(f)
        if cid in db.get("players", {}):
            db["players"][cid]["name"] = new_name
            with open(career_path, "w", encoding="utf-8") as f:
                json.dump(db, f, indent=2)


# ---------------------------------------------------------
# Ranking tags (shared between the on-screen Rankings popup and the
# auto-exported HTML pages, so both always agree)
# ---------------------------------------------------------

RANKING_TAGS = [
    "Slayer",
    "Payload Objective Specialist",
    "Sharpshooter",
    "Domination Objective Specialist",
    "Consistency",
    "Clutch",
    "Anchor",
    "Breaker",
]

RANKING_TAG_SLUGS = {
    "Slayer": "slayer",
    "Payload Objective Specialist": "payload",
    "Sharpshooter": "sharpshooter",
    "Domination Objective Specialist": "domination",
    "Consistency": "consistency",
    "Clutch": "clutch",
    "Anchor": "anchor",
    "Breaker": "breaker",
}

RANKING_FORMULAS = {
    "Slayer": [
        "Slayer Formula:",
        "Slayer Score = (Damage per Map × 0.40) + (Kills per Map × 0.40) + (KD × 0.20)",
    ],
    "Sharpshooter": [
        "Sharpshooter Formula:",
        "Sharpshooter = (Accuracy × 0.40) + (Headshot Rate × 0.40) + (Damage per Shot × 0.20)",
        "Where:",
        "- Accuracy = Shots Hit / Shots Fired",
        "- Headshot Rate = Headshots / Shots Hit",
        "- Damage per Shot = Damage / Shots Fired",
    ],
    "Payload Objective Specialist": [
        "Payload Objective Formula:",
        "ObjPL = (Presence × 0.40) + (PushTime Normalized × 0.40) + (PSI × 0.20)",
        "Where:",
        "- Presence = Player PushTime / Team PushTime",
        "- PSI = Damage / (Deaths + 1) × 1 / sqrt(PushTime + 1)",
    ],
    "Domination Objective Specialist": [
        "Domination Objective Formula:",
        "ObjDOM = (CapRate × 0.40) + (CounterRate × 0.60)",
        "Where:",
        "- CapRate = log(1 + DOM_captures) / log(21)",
        "- CounterRate = log(1 + DOM_counters) / log(21)",
        "Counters are weighted more heavily because they prevent enemy scoring.",
    ],
    "Consistency": [
        "Consistency Formula (Hybrid Career Tag):",
        "Consistency = (Floor × 0.40) + (Stability × 0.40) + (Average Performance × 0.20)",
        "Where:",
        "- Floor = lowest per-match performance score",
        "- Stability = 1 / (1 + Adjusted Variance)",
        "- Adjusted Variance = Variance × (1 + 1 / Match Count)",
        "- Average Performance = mean per-match performance score",
    ],
    "Clutch": [
        "Clutch Formula:",
        "Clutch = (Pressure Efficiency × 0.40) + (Collapse Avoidance × 0.40) + (Conversion Rate × 0.20)",
        "Where:",
        "- Pressure Efficiency = Damage / (Deaths + 1)",
        "- Collapse Avoidance = Player's lowest per-map performance score",
        "- Conversion Rate = (Accuracy × 0.50) + (Headshot Rate × 0.50)",
    ],
    "Anchor": [
        "Anchor Formula:",
        "Anchor = (Survivability × 0.45) + (DefensivePresence × 0.30) + (Consistency × 0.25)",
        "Where:",
        "- Survivability = (LeagueAvgDeathsPerMap / PlayerDeathsPerMap), clamped to [0.25, 1.50] then normalized to 0–1",
        "- DefensivePresence = (DamagePerMap / LeagueAvgDamagePerMap), clamped to [0, 1.5] then normalized to 0–1",
        "- Consistency = normalized 0–1 stability score from the Consistency tag",
        "Survivability reflects how hard the player is to remove; Defensive Presence measures baseline contribution; Consistency rewards stable defensive performance.",
    ],
    "Breaker": [
        "Breaker Formula:",
        "Breaker = (DamageNorm × 0.60) + (KillsNorm × 0.40)",
        "Where:",
        "- DamageNorm = Damage per map normalized against league average",
        "- KillsNorm = Kills per map normalized against league average",
        "Breaker measures disruptive offensive pressure through high damage output and aggressive fragging.",
    ],
}


class DashLeagueGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("DashLeague Casting Tool")

        self.config = {}
        self.current_season = None
        self.team_a_var = tk.StringVar()
        self.team_b_var = tk.StringVar()

        self.team_a_players = []
        self.team_b_players = []
        self.stats_by_id = {}

        self.status_var = tk.StringVar(value="Ready")

        self.load_config()
        ensure_player_slots()
        self._build_ui()

        self.current_match_players = []
        self.start_local_obs_server()

    def start_local_obs_server(self):
        """
        Serves the obs_exports folder over http://localhost:PORT instead
        of file:// paths. OBS Browser Sources (and browsers generally)
        block fetch() on file:// URLs by default as a security
        restriction, which silently breaks the auto-refresh polling
        script embedded in every exported HTML page — the fetch just
        fails and the page never notices it's stale. Serving over
        http:// avoids that entirely. Point OBS Browser Sources at
        http://localhost:{port}/matchup.html etc. instead of a local
        file path, and the auto-refresh will work reliably.

        Safe to call again after the output folder changes — stops any
        previously running server first so it always serves the
        current export directory.
        """
        export_dir = os.path.join(self.output_root, "obs_exports") if getattr(self, "output_root", None) else OBS_EXPORT_DIR
        os.makedirs(export_dir, exist_ok=True)

        existing = getattr(self, "_obs_httpd", None)
        if existing:
            try:
                existing.shutdown()
                existing.server_close()
            except Exception:
                pass
            self._obs_httpd = None

        handler = functools.partial(SimpleHTTPRequestHandler, directory=export_dir)
        try:
            httpd = HTTPServer(("localhost", LOCAL_OBS_SERVER_PORT), handler)
        except OSError as e:
            print(f"Local OBS server could not start on port {LOCAL_OBS_SERVER_PORT}: {e}")
            self.set_status(f"Note: local OBS server unavailable (port {LOCAL_OBS_SERVER_PORT} busy) — auto-refresh may need manual toggling.")
            return

        self._obs_httpd = httpd
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        print(f"Local OBS server running at http://localhost:{LOCAL_OBS_SERVER_PORT}/ (serving {export_dir})")
       

    def load_config(self):
        if not os.path.exists(CONFIG_PATH):
            messagebox.showerror("Error", f"config.json not found at {CONFIG_PATH}")
            self.config = {}
            return
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self.current_season = self.config.get("current_season", 11)
        # Restore previously-selected output folder (if any) so the user
        # doesn't have to re-click "Select Output Folder" every launch.
        self.output_root = self.config.get("output_root")

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        self.team_a_var = tk.StringVar()
        self.team_b_var = tk.StringVar()

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        top_frame = ttk.Frame(main_frame)
        top_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        
        self.build_db_button = ttk.Button(top_frame, text="Build Career Database", command=self.on_build_career_db)
        self.build_db_button.grid(row=0, column=0, padx=(0, 10))

        self.sync_button = ttk.Button(top_frame, text="Sync Stats", command=self.on_sync_stats)
        self.sync_button.grid(row=0, column=1, padx=(0, 10))

        self.team_id_button = ttk.Button(top_frame, text="Team Identity", command=self.on_team_identity)
        self.team_id_button.grid(row=0, column=2, padx=(0, 10))

        self.storyline_button = ttk.Button(top_frame, text="Match Storyline", command=self.on_match_storyline)
        self.storyline_button.grid(row=0, column=3, padx=(0, 10))

        self.rankings_button = ttk.Button(top_frame, text="Rankings", command=self.on_rankings)
        self.rankings_button.grid(row=0, column=4, padx=(0, 10))
        
        self.rookie_button = ttk.Button(top_frame, text="Rookie Leaderboard", command=self.on_rookie_leaderboard)
        self.rookie_button.grid(row=0, column=5, padx=(0, 10))

        self.manage_roster_button = ttk.Button(top_frame, text="Manage Roster/Names", command=self.open_roster_manager)
        self.manage_roster_button.grid(row=0, column=6, padx=(0, 10))
        
        self.output_folder_button = ttk.Button(
            top_frame,
            text="Select Output Folder",
            command=self.choose_output_folder
        )
        self.output_folder_button.grid(row=0, column=7, padx=(0, 10))
        
        self.map_var = tk.StringVar()
        self.map_var.set("Payload")  # default

        teams = self.config.get("teams", [])

        left_frame = ttk.LabelFrame(main_frame, text="Team A")
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
        right_frame = ttk.LabelFrame(main_frame, text="Team B")
        right_frame.grid(row=1, column=1, sticky="nsew", padx=(5, 0))

        main_frame.rowconfigure(1, weight=1)
        left_frame.rowconfigure(1, weight=1)
        right_frame.rowconfigure(1, weight=1)

        ttk.Label(left_frame, text="Team:").grid(row=0, column=0, sticky="w")
        self.team_a_combo = ttk.Combobox(left_frame, textvariable=self.team_a_var, values=teams, state="readonly")
        self.team_a_combo.grid(row=0, column=1, sticky="ew", pady=2)
        self.team_a_combo.bind("<<ComboboxSelected>>", lambda e: self.on_team_select("A"))

        ttk.Label(right_frame, text="Team:").grid(row=0, column=0, sticky="w")
        self.team_b_combo = ttk.Combobox(right_frame, textvariable=self.team_b_var, values=teams, state="readonly")
        self.team_b_combo.grid(row=0, column=1, sticky="ew", pady=2)
        self.team_b_combo.bind("<<ComboboxSelected>>", lambda e: self.on_team_select("B"))

        self.team_a_listbox = tk.Listbox(left_frame, selectmode=tk.MULTIPLE, exportselection=False)
        self.team_a_listbox.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(5, 0))

        self.team_b_listbox = tk.Listbox(right_frame, selectmode=tk.MULTIPLE, exportselection=False)
        self.team_b_listbox.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(5, 0))
        
        self.team_a_listbox.bind("<<ListboxSelect>>", lambda e: self.enforce_rolling_five(e, "A"))
        self.team_b_listbox.bind("<<ListboxSelect>>", lambda e: self.enforce_rolling_five(e, "B"))

        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        self.generate_button = ttk.Button(bottom_frame, text="Generate Player Slots", command=self.on_generate_slots)
        self.generate_button.grid(row=0, column=0, sticky="ew")
        
        ttk.Label(bottom_frame, text="Map:").grid(row=0, column=1, padx=(10, 5))
        ttk.OptionMenu(bottom_frame, self.map_var, "Payload", "Payload", "Domination").grid(row=0, column=2)
        
        # Create a specific section for the 4K Graphics
        broadcast_frame = ttk.LabelFrame(main_frame, text="4K Broadcast Graphics", padding=10)
        broadcast_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        ttk.Button(broadcast_frame, text="Player Spotlight", command=self.on_player_spotlight).grid(row=0, column=0, padx=5)
        ttk.Button(broadcast_frame, text="Tale of the Tape (PvP)", command=self.on_tale_of_the_tape).grid(row=0, column=1, padx=5)
        ttk.Button(broadcast_frame, text="Team vs Team (DNA)", command=self.on_team_comparison).grid(row=0, column=2, padx=5)
        ttk.Button(broadcast_frame, text="Win Probability", command=self.on_win_probability).grid(row=0, column=3, padx=5)
        

        status_frame = ttk.Frame(self.root)
        status_frame.grid(row=1, column=0, sticky="ew")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor="w")
        status_label.grid(row=0, column=0, sticky="ew")
        status_frame.columnconfigure(0, weight=1)

    def set_status(self, text):
        self.status_var.set(text)
        self.root.update_idletasks()
        
        
    # Add these methods inside the DashLeagueGUI class

    def get_team_roster_data(self, team_name):
        """
        Helper to get full career data for the current 5-man roster, for
        use ONLY in the three team-comparison graphics (Tale of the Tape,
        Team DNA, Win Probability).

        Priority order per player:
          1. Real career_stats.json data, if present.
          2. Their OWN verified current-season stats (from
             on_generate_slots step 4.5's per-player API fetch) if
             available — a real, if season-only, number is far more
             accurate than a teammate average and should be used
             directly, not discarded.
          3. A temporary, in-memory average of THIS TEAM's other players
             (not the whole league) as an absolute last resort, only for
             players with genuinely no data of any kind. Never saved to
             career_stats.json, never used on their personal Spotlight
             card.

        IMPORTANT: that team-local average is built from every OTHER
        teammate who has real data — including verified current-season
        stats, which only ever exist in memory on self.current_match_
        players, never on disk. Previously the average was computed
        purely from career_stats.json on disk, so if most of a team's
        real data came from verified fetches rather than the career
        database, the average pool came up empty and silently returned
        all zeros — which looked exactly like a player with no stats at
        all, and skewed the whole comparison graphic.
        """
        career_path = os.path.join(BASE_DIR, "career_stats.json")
        with open(career_path, "r", encoding="utf-8") as f:
            db = json.load(f)

        team_players = [p for p in self.current_match_players if p.get("team") == team_name]

        # First pass: classify every player and collect the REAL
        # (career or verified) career dicts as we go.
        resolved = []
        real_careers = []

        for p in team_players:
            cid = p.get("canonical")
            if not cid:
                continue

            pdata = db["players"].get(cid)
            if pdata and pdata.get("career"):
                resolved.append((p, "real", pdata))
                real_careers.append(pdata["career"])
                continue

            kills = p.get("kills", 0) or 0
            deaths = p.get("deaths", 0) or 0
            if p.get("_verified_season_stats") and (kills or deaths or p.get("damage")):
                own_career = {
                    "kills": kills,
                    "deaths": deaths,
                    "damage": p.get("damage", 0) or 0,
                    "maps": p.get("maps", 0) or 0,
                    "KD": (kills / deaths) if deaths > 0 else kills,
                    "score": p.get("score", 0) or 0,
                }
                resolved.append((p, "verified", own_career))
                real_careers.append(own_career)
                continue

            resolved.append((p, "new", None))

        # Team-local average built from every teammate with REAL data
        # (career or verified), computed once, lazily, only if at least
        # one player on this team actually needs it.
        team_avg = None
        needs_avg = any(mode == "new" for _, mode, _ in resolved)
        if needs_avg and real_careers:
            totals = {field: 0.0 for field in CAREER_AVERAGE_FIELDS}
            for career in real_careers:
                for field in CAREER_AVERAGE_FIELDS:
                    totals[field] += career.get(field, 0) or 0
            team_avg = {field: totals[field] / len(real_careers) for field in CAREER_AVERAGE_FIELDS}

        roster_data = []
        for p, mode, extra in resolved:
            cid = p.get("canonical")
            name = p.get("name") or cid

            if mode == "real":
                p_data = dict(extra)
                p_data["current_team"] = team_name
                p_data["stats_estimated"] = False
                roster_data.append(p_data)
                continue

            if mode == "verified":
                pdata = db["players"].get(cid)
                p_data = dict(pdata) if pdata else {"name": name}
                p_data["name"] = name
                p_data["current_team"] = team_name
                p_data["career"] = extra
                p_data["stats_estimated"] = False
                # Generate Player Slots already computed real, season-
                # based skill percentiles for this player (career-first/
                # live-fallback system, ranked against the real league
                # distribution) — they're sitting on p. Without copying
                # them here, Tale of the Tape / Team DNA / Win
                # Probability (which all read p.get(tag, {}).get("pct"),
                # not the career dict) would silently show 0% for every
                # tag for this player, dragging team averages down as if
                # they contributed nothing.
                for tag in ("slayer", "sharpshooter", "objective_payload", "objective_domination", "consistency", "clutch", "anchor", "breaker"):
                    tag_data = p.get(tag)
                    if tag_data:
                        p_data[tag] = tag_data
                p_data["career_note"] = (
                    f"{name}'s numbers are from verified current-season data only — "
                    f"no prior-season career history on file yet."
                )
                roster_data.append(p_data)
                continue

            # mode == "new": genuinely nothing to go on for this player.
            pdata = db["players"].get(cid)
            p_data = dict(pdata) if pdata else {"name": name}
            p_data["name"] = name
            p_data["current_team"] = team_name
            p_data["stats_estimated"] = True

            if team_avg:
                p_data["career"] = dict(team_avg)
                p_data["career_note"] = (
                    f"NEW PLAYER — no career stats yet. Numbers shown for this "
                    f"comparison are a temporary {team_name} teammate average, "
                    f"not {name}'s actual performance."
                )
            else:
                # No teammates with real data either — be explicit
                # about it rather than silently showing zeros with no
                # explanation, which is what was throwing the graphs off.
                p_data["career"] = {field: 0 for field in CAREER_AVERAGE_FIELDS}
                p_data["career_note"] = (
                    f"NEW PLAYER — no career stats yet, and no teammates with "
                    f"real data to average either. This comparison has no "
                    f"reliable numbers for {name}; treat it with caution."
                )
            roster_data.append(p_data)
        return roster_data

    def on_tale_of_the_tape(self):
        if not self.current_match_players:
            messagebox.showerror("Error", "Generate Player Slots first.")
            return

        team_a = self.team_a_var.get()
        team_b = self.team_b_var.get()

        export_dir = self.require_output_folder()
        if not export_dir:
            return

        roster_a = self.get_team_roster_data(team_a)
        roster_b = self.get_team_roster_data(team_b)

        from utils.graphics_engine import generate_tale_of_the_tape
        try:
            generate_tale_of_the_tape(roster_a, roster_b, team_a, team_b, export_dir=export_dir)
            self.set_status("Generated 4K Tale of the Tape (PvP)")

            from analysis.html_export import render_spotlight_html
            wrapper_html = render_spotlight_html("tale_of_the_tape.png")
            with open(os.path.join(export_dir, "tale_of_the_tape.html"), "w", encoding="utf-8") as f:
                f.write(wrapper_html)

            messagebox.showinfo("Success", "PvP Graphic generated in obs_exports.")
        except Exception as e:
            messagebox.showerror("Graphics Error", str(e))

    def on_team_comparison(self):
        if not self.current_match_players:
            messagebox.showerror("Error", "Generate Player Slots first.")
            return

        team_a = self.team_a_var.get()
        team_b = self.team_b_var.get()

        export_dir = self.require_output_folder()
        if not export_dir:
            return

        roster_a = self.get_team_roster_data(team_a)
        roster_b = self.get_team_roster_data(team_b)

        from utils.graphics_engine import generate_team_dna
        try:
            generate_team_dna(roster_a, roster_b, team_a, team_b, export_dir=export_dir)
            self.set_status("Generated 4K Team DNA Graphic")

            from analysis.html_export import render_spotlight_html
            wrapper_html = render_spotlight_html("team_dna.png")
            with open(os.path.join(export_dir, "team_dna.html"), "w", encoding="utf-8") as f:
                f.write(wrapper_html)

            messagebox.showinfo("Success", "Team DNA Graphic generated in obs_exports.")
        except Exception as e:
            messagebox.showerror("Graphics Error", str(e))    

            
    def on_win_probability(self):
        if not self.current_match_players:
            messagebox.showerror("Error", "Generate Player Slots first.")
            return

        team_a = self.team_a_var.get()
        team_b = self.team_b_var.get()
        export_dir = self.require_output_folder()
        if not export_dir:
            return

        roster_a = self.get_team_roster_data(team_a)
        roster_b = self.get_team_roster_data(team_b)

        from utils.graphics_engine import generate_win_probability
        try:
            generate_win_probability(roster_a, roster_b, team_a, team_b, export_dir=export_dir)
            self.set_status("Generated 4K Win Probability Graphic")

            from analysis.html_export import render_spotlight_html
            wrapper_html = render_spotlight_html("win_probability.png")
            with open(os.path.join(export_dir, "win_probability.html"), "w", encoding="utf-8") as f:
                f.write(wrapper_html)

            messagebox.showinfo("Success", "Win Probability Graphic generated in obs_exports.")
        except Exception as e:
            messagebox.showerror("Graphics Error", str(e))   
            

    def on_sync_stats(self):
        try:
            self.set_status(f"Syncing stats for season {self.current_season}...")
            url = f"{API_BASE}/stats?season={self.current_season}"
            data = fetch_json(url)
            stats = data.get("data", [])

            # ---------------------------------------------------------
            # Load PIR + Career DB
            # ---------------------------------------------------------
            from analysis.player_identity_registry import PlayerIdentityRegistry
            pir = PlayerIdentityRegistry()

            career_path = os.path.join(BASE_DIR, "career_stats.json")
            with open(career_path, "r", encoding="utf-8") as f:
                career_db = json.load(f)

            players_db = career_db.setdefault("players", {})

            # ---------------------------------------------------------
            # BUILD stats_by_id (canonical → enriched player object)
            # ---------------------------------------------------------
            new_stats_by_id = {}

            for p in stats:
                raw_id = p.get("id")
                if not raw_id:
                    continue

                # Resolve canonical + stamp seasons
                canonical = pir.resolve(raw_id, season=self.current_season)

                # Update Registry and History with clean names
                clean_name = p.get("name")
                clean_team = (p.get("team") or "").strip()
                
                pir.update_name(canonical, clean_name)
                if clean_team:
                    pir.update_team(canonical, clean_team)

                # Ensure career_stats has this history
                if canonical in players_db:
                    players_db[canonical]["team_history"] = pir.data["canonical"][canonical]["team_history"]
                
                if not canonical:
                    continue

                # Ensure first_season is set if missing
                entry = pir.data["canonical"].get(canonical)

                # Normalize DOM fields from API (for DomObj)
                p["DOM_Captures"] = p.get("DOM_captures", p.get("DOM_Captures", 0))
                p["DOM_Counters"] = p.get("DOM_counters", p.get("DOM_Counters", 0))

                merged = {
                    "canonical": canonical,
                    "name": p.get("name"),
                    "team": (p.get("team") or "").strip(),
                    "id": raw_id,
                    "kills": p.get("kills", 0),
                    "deaths": p.get("deaths", 0),
                    "damage": p.get("damage", 0),
                    "shots": p.get("shots", 0),
                    "shots_hit": p.get("shots_hit", 0),
                    "headshots": p.get("headshots", 0),
                    "PAY_PushTime": p.get("PAY_PushTime", 0),
                    "CP_Captures": p.get("CP_captures", p.get("CP_Captures", 0)),
                    # The API actually gives us maps played directly —
                    # no need to estimate it from deaths.
                    "maps": p.get("maps", 0),
                    "playtime_minutes": p.get("Total PlayTime", 0),
                    "wins": p.get("wins", 0),
                    "loss": p.get("loss", 0),
                    "match_stats": p,
                    "seasons_played": p.get("seasons_played") or p.get("seasons") or "",
                }

                # Ensure player exists in career DB (so rookies are present)
                if canonical not in players_db:
                    players_db[canonical] = {
                        "name": merged["name"],
                        "team_history": [merged["team"]] if merged["team"] else [],
                        "seasons_played": merged.get("seasons_played"),
                        "slayer": {},
                        "sharpshooter": {},
                        "objective_payload": {},
                        "objective_domination": {},
                        "consistency": {},
                        "clutch": {},
                        "anchor": {},
                        "breaker": {},
                    }

                pdata = players_db.setdefault(canonical, {})
                pdata["seasons_played"] = merged["seasons_played"]
                # Always refresh the stored name, not just on first creation—
                # otherwise a renamed player keeps showing their original
                # in-game name forever on the Spotlight card and graphics,
                # even though the identity registry correctly tracks the
                # rename.
                if merged.get("name"):
                    pdata["name"] = merged["name"]

                # Store basic stats into career DB so rookies have real data
                pdata["kills"] = merged.get("kills", 0)
                pdata["deaths"] = merged.get("deaths", 0)
                pdata["damage"] = merged.get("damage", 0)
                pdata["shots"] = merged.get("shots", 0)
                pdata["shots_hit"] = merged.get("shots_hit", 0)
                pdata["headshots"] = merged.get("headshots", 0)
                pdata["maps"] = merged.get("maps", 0)
                pdata["PAY_PushTime"] = merged.get("PAY_PushTime", 0)

                # Score is inside match_stats
                ms = merged.get("match_stats", {})
                pdata["score"] = ms.get("score", 0)

                # KD
                if pdata["deaths"] > 0:
                    pdata["kd"] = pdata["kills"] / pdata["deaths"]
                else:
                    pdata["kd"] = pdata["kills"]

                # Attach career tags
                for tag in (
                    "slayer",
                    "sharpshooter",
                    "objective_payload",
                    "objective_domination",
                    "consistency",
                    "clutch",
                    "anchor",
                    "breaker",
                ):
                    merged[tag] = pdata.get(tag, {})

                new_stats_by_id[canonical] = merged
                
                # Write merged stats into career DB
                players_db[canonical]["kills"] = merged["kills"]
                players_db[canonical]["deaths"] = merged["deaths"]
                players_db[canonical]["damage"] = merged["damage"]
                players_db[canonical]["shots"] = merged["shots"]
                players_db[canonical]["shots_hit"] = merged["shots_hit"]
                players_db[canonical]["headshots"] = merged["headshots"]
                players_db[canonical]["maps"] = merged["maps"]
                players_db[canonical]["PAY_PushTime"] = merged["PAY_PushTime"]
                players_db[canonical]["match_stats"] = merged["match_stats"]
                players_db[canonical]["seasons_played"] = merged["seasons_played"]

                # Compute KD
                d = merged["deaths"]
                players_db[canonical]["kd"] = merged["kills"] / d if d > 0 else merged["kills"]

                # Score (inside match_stats)
                players_db[canonical]["score"] = merged["match_stats"].get("score", 0)

            # ---------------------------------------------------------
            # Save updated career DB (rookies now included)
            # ---------------------------------------------------------
            with open(career_path, "w", encoding="utf-8") as f:
                json.dump(career_db, f, indent=2)

            # ---------------------------------------------------------
            # Save PIR (first_season now persisted)
            # ---------------------------------------------------------
            pir.save()

            # ---------------------------------------------------------
            # Replace stats_by_id with enriched version
            # ---------------------------------------------------------
            self.stats_by_id = new_stats_by_id

            self.set_status("Stats synced.")
            messagebox.showinfo("Success", f"Synced {len(stats)} player stats.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to sync stats:\n{e}")
            self.set_status("Sync failed.")

        # Re-trigger team selection so listboxes repopulate
        if self.team_a_var.get():
            self.on_team_select("A")
        if self.team_b_var.get():
            self.on_team_select("B")

    
    def enforce_rolling_five(self, event, side):
        listbox = self.team_a_listbox if side == "A" else self.team_b_listbox
        selection = listbox.curselection()

        # If 5 or fewer selected, nothing to do
        if len(selection) <= 5:
            return

        # More than 5 selected → rolling behavior:
        # Deselect the *oldest* selected index
        oldest = selection[0]
        listbox.selection_clear(oldest)
            
            
    def on_team_select(self, side):
        team_name = self.team_a_var.get() if side == "A" else self.team_b_var.get()

        from analysis.player_identity_registry import PlayerIdentityRegistry
        pir = PlayerIdentityRegistry()
        overrides = load_roster_overrides()

        matching = []
        seen_canonical = set()

        # 1. Players with live stats this season whose CURRENT team (manual
        #    override takes priority, else match-derived team_history)
        #    matches. This correctly re-homes a player to their new team
        #    even if their most recent synced match was still under their
        #    old team (e.g. hasn't played a match since a merge yet).
        for p in self.stats_by_id.values():
            cid = p.get("canonical")
            current_team = get_current_team(cid, pir, overrides) if cid else (p.get("team") or p.get("TeamUUID"))
            if current_team == team_name:
                p["team"] = team_name
                matching.append(p)
                if cid:
                    seen_canonical.add(cid)

        # 2. Everyone else whose CURRENT team matches, even with no live
        #    stats yet this season (new to the team, roster merge, hasn't
        #    taken the field yet, etc). Without this, rostered players who
        #    simply haven't played a synced match silently disappear.
        #
        #    RECENCY GUARD: team_history only ever gets a new entry when a
        #    player JOINS a new team — nothing marks them as having left.
        #    So a player who quit the league years ago while on this team
        #    would otherwise stay listed on its roster forever, inflating
        #    it past the real ~12-man cap. Players who haven't appeared in
        #    a synced match for more than one season are excluded here
        #    UNLESS a caster has explicitly placed them on this team via
        #    Manage Roster — an explicit override always wins.
        RECENCY_WINDOW = 1
        for cid, entry in pir.data.get("canonical", {}).items():
            if cid in seen_canonical:
                continue
            current_team = get_current_team(cid, pir, overrides)
            if current_team != team_name:
                continue

            has_override = cid in overrides
            last_season = entry.get("last_season")
            is_recent = (
                last_season is None
                or self.current_season is None
                or last_season >= self.current_season - RECENCY_WINDOW
            )
            if not has_override and not is_recent:
                continue

            display_name = entry["names"][-1] if entry.get("names") else cid
            matching.append({
                "canonical": cid,
                "name": display_name,
                "team": team_name,
                "id": cid,
                "kills": 0,
                "deaths": 0,
                "damage": 0,
                "shots": 0,
                "shots_hit": 0,
                "match_stats": {},
                "seasons_played": "",
                "slayer": {},
                "sharpshooter": {},
                "objective_payload": {},
                "objective_domination": {},
                "consistency": {},
                "clutch": {},
                "anchor": {},
                "breaker": {},
            })
            seen_canonical.add(cid)

        # Now assign to UI
        if side == "A":
            self.team_a_players = matching
            self.team_a_listbox.delete(0, tk.END)
            for p in matching:
                self.team_a_listbox.insert(tk.END, p.get("name", "Unknown"))
        else:
            self.team_b_players = matching
            self.team_b_listbox.delete(0, tk.END)
            for p in matching:
                self.team_b_listbox.insert(tk.END, p.get("name", "Unknown"))
                
                
    def normalize_player(self, p):
        return {
            "id": p.get("id"),
            "name": p.get("name"),
            "team": p.get("team"),
            "KD": p.get("KD", 0),
            "kills": p.get("kills", 0),
            "deaths": p.get("deaths", 0),
            "headshots": p.get("headshots", 0),
            "accuracy": p.get("accuracy", 0),
            "PAY_PushTime": p.get("PAY_PushTime", 0),
            "DOM_captures": p.get("DOM_captures", 0),
            "DOM_counters": p.get("DOM_counters", 0),
        }             
                
                

    def on_generate_slots(self):
        try:
            ensure_player_slots()

            # ---------------------------------------------------------
            # 1. Collect selected players
            # ---------------------------------------------------------
            selected_a = [self.team_a_players[i] for i in self.team_a_listbox.curselection()]
            selected_b = [self.team_b_players[i] for i in self.team_b_listbox.curselection()]

            if not selected_a:
                selected_a = self.team_a_players
            if not selected_b:
                selected_b = self.team_b_players

            # Limit to 5 per team
            selected_a = selected_a[:5]
            selected_b = selected_b[:5]
            all_players = selected_a + selected_b

            # ---------------------------------------------------------
            # 2. Normalize stat keys BEFORE attaching tags
            # ---------------------------------------------------------

            for p in all_players:
                ms = p.get("match_stats", {})

                # DOM
                p["DOM_Captures"] = (
                    p.get("DOM_Captures") 
                    or p.get("DOM_captures") 
                    or ms.get("DOM_Captures") 
                    or ms.get("DOM_captures") 
                    or 0
                )

                p["DOM_Counters"] = (
                    p.get("DOM_Counters")
                    or p.get("DOM_counters")
                    or ms.get("DOM_Counters")
                    or ms.get("DOM_counters")
                    or 0
                )

            # ---------------------------------------------------------
            # 3. Resolve canonical IDs AND normalize player ID
            # ---------------------------------------------------------
            from analysis.player_identity_registry import PlayerIdentityRegistry
            pir = PlayerIdentityRegistry()

            for p in all_players:
                # If this player already has a valid canonical ID (set by
                # on_team_select — true for both live-synced players AND
                # roster stub players who haven't played a match yet),
                # do NOT re-resolve it. Stub players have their "id" set
                # to their canonical string itself as a placeholder, not
                # a real UUID; feeding that into pir.resolve() as if it
                # were a raw UUID mints a brand new, bogus canonical ID
                # with no career data, silently corrupting an already-
                # correct resolution and making established players
                # (e.g. anyone added via Manage Roster) look brand new.
                if p.get("canonical"):
                    continue

                raw_uuid = (
                    p.get("id")
                    or p.get("PlayerUUID")
                    or p.get("uuid")
                )
                if raw_uuid:
                    p["canonical"] = pir.resolve(raw_uuid, season=self.current_season)

                # Normalize ID (AFTER canonical resolution)
                pid = (
                    p.get("id")
                    or p.get("PlayerUUID")
                    or p.get("uuid")
                    or p.get("canonical")
                    or p.get("name")
                )
                p["id"] = pid

            # ---------------------------------------------------------
            # 4. Load career DB once
            # ---------------------------------------------------------
            career_db = None
            career_path = os.path.join(BASE_DIR, "career_stats.json")
            if os.path.exists(career_path):
                with open(career_path, "r", encoding="utf-8") as f:
                    career_db = json.load(f)

            # ---------------------------------------------------------
            # 4.5 For any player missing from career_stats.json, fetch
            #     their EXACT current-season stats directly from
            #     /api/v1/player?PlayerID=X (confirmed to return a
            #     precise per-season breakdown: real maps, kills,
            #     deaths, damage, shots, shots_hit, headshots,
            #     CP_captures, PAY_PushTime, DOM_captures/counters).
            #     This replaces the deaths-based/subtraction guesses
            #     with real, verified numbers wherever the API call
            #     succeeds — only costs one extra request per player who
            #     actually needs it (typically a handful per match, not
            #     the whole roster). If the call fails for any reason
            #     (offline, unknown player, etc.), the existing
            #     estimate-based fallback in resolve_tag_career_first
            #     still applies as a safety net.
            # ---------------------------------------------------------
            for p in all_players:
                cid = p.get("canonical")
                pdata = career_db["players"].get(cid) if (career_db and cid) else None
                has_career = pdata and pdata.get("slayer") and pdata["slayer"].get("raw") is not None
                if has_career:
                    continue

                entry = pir.data.get("canonical", {}).get(cid, {}) if cid else {}
                uuids = entry.get("uuids") or []
                raw_uuid = uuids[-1] if uuids else (p.get("uuid") or p.get("PlayerUUID"))
                if not raw_uuid or str(raw_uuid).startswith("player_"):
                    continue  # no real UUID available for this player

                season_stats = fetch_player_season_stats(raw_uuid, self.current_season)
                if not season_stats:
                    continue

                p["kills"] = season_stats.get("kills", p.get("kills", 0))
                p["deaths"] = season_stats.get("deaths", p.get("deaths", 0))
                p["damage"] = season_stats.get("damage", p.get("damage", 0))
                p["score"] = season_stats.get("score", p.get("score", 0))
                p["shots"] = season_stats.get("shots", p.get("shots", 0))
                p["shots_hit"] = season_stats.get("shots_hit", p.get("shots_hit", 0))
                p["headshots"] = season_stats.get("headshots", p.get("headshots", 0))
                p["maps"] = season_stats.get("maps", p.get("maps", 0))
                p["PAY_PushTime"] = season_stats.get("PAY_PushTime", p.get("PAY_PushTime", 0))
                p["CP_Captures"] = season_stats.get("CP_captures", p.get("CP_Captures", 0))
                p["DOM_Captures"] = season_stats.get("DOM_captures", p.get("DOM_Captures", 0))
                p["DOM_Counters"] = season_stats.get("DOM_counters", p.get("DOM_Counters", 0))
                p["_verified_season_stats"] = True

            # ---------------------------------------------------------
            # 5. Resolve every tag career-first, with a live-sync
            #    fallback for anyone missing from career_stats.json
            #    (e.g. missing from match_history.db, which only covers
            #    past seasons and never picks up current-season
            #    activity). See resolve_tag_career_first for details.
            #    Fallback players are marked has_data=False so they're
            #    excluded from team averages/predictions rather than
            #    silently counted as a real score of zero. Domination
            #    Objective now goes through this same unified system
            #    (see compute_fallback_domination) instead of its own
            #    separate, unbounded formula.
            # ---------------------------------------------------------
            for tag_name, (fallback_fn, label) in FALLBACK_FORMULAS.items():
                resolve_tag_career_first(all_players, tag_name, career_db, fallback_fn, label)

            # ---------------------------------------------------------
            # 6. Consistency — special-cased. It fundamentally needs
            #    per-match variance data that can't be reconstructed
            #    from season-cumulative totals alone, so there's no
            #    honest live-sync fallback formula for it the way there
            #    is for the other tags. Use real career consistency when
            #    available; otherwise mark it no-data (neutral raw,
            #    excluded from averages) instead of inventing a number.
            # ---------------------------------------------------------
            consistency_rows = rank_match_players_consistency_career(all_players)
            consistency_map = {row["id"]: row for row in consistency_rows}

            for p in all_players:
                row = consistency_map.get(p["id"])
                if row and row.get("has_data"):
                    p["consistency"] = {
                        "raw": row["score_raw"],
                        "pct": row.get("pct"),
                        "tier": row.get("tier"),
                        "has_data": True,
                        "summary": f"{row.get('tier','?')} Tier ({row.get('pct',0) or 0:.1f} percentile)" if row.get("pct") is not None else "",
                    }
                else:
                    p["consistency"] = {
                        "raw": 0.5,
                        "pct": None,
                        "tier": None,
                        "has_data": False,
                        "summary": "No career match history available to measure consistency.",
                    }

            # ---------------------------------------------------------
            # 7. (Domination Objective is now handled in step 5 above,
            #    as part of the unified FALLBACK_FORMULAS system.)
            # ---------------------------------------------------------

            # 11. Ensure stats_by_id contains all enriched tags
            for p in all_players:
                cid = p.get("canonical")
                if not cid:
                    continue

                enriched = self.stats_by_id.get(cid)
                if not enriched:
                    continue

                # Copy match fields into stats_by_id
                enriched["team"] = p.get("team")
                enriched["name"] = p.get("name")
                enriched["id"] = p.get("id")

            # ---------------------------------------------------------
            # 12. Update current_match_players
            # ---------------------------------------------------------
            self.current_match_players = all_players

            # ---------------------------------------------------------
            # 13. Write OBS slot files
            # ---------------------------------------------------------
            for idx, p in enumerate(all_players):
                slot_dir = os.path.join(PLAYERS_DIR, f"p{idx}")
                os.makedirs(slot_dir, exist_ok=True)

                write_text(os.path.join(slot_dir, "IGN.txt"), p.get("name", ""))
                write_text(os.path.join(slot_dir, "Team.txt"), p.get("team", ""))

                write_text(os.path.join(slot_dir, "KD.txt"), p.get("KD", ""))
                write_text(os.path.join(slot_dir, "Kills.txt"), p.get("kills", ""))
                write_text(os.path.join(slot_dir, "Deaths.txt"), p.get("deaths", ""))
                write_text(os.path.join(slot_dir, "Headshots.txt"), p.get("headshots", ""))
                write_text(os.path.join(slot_dir, "Accuracy.txt"), p.get("accuracy", ""))

                write_text(os.path.join(slot_dir, "PushTime.txt"), p.get("PAY_PushTime", ""))
                write_text(os.path.join(slot_dir, "Captures.txt"), p.get("DOM_Captures", ""))
                write_text(os.path.join(slot_dir, "Counters.txt"), p.get("DOM_Counters", ""))

                # Consistency
                write_text(os.path.join(slot_dir, "ConsistencyRaw.txt"), p["consistency"]["raw"])
                write_text(os.path.join(slot_dir, "ConsistencyPct.txt"), p["consistency"]["pct"])
                write_text(os.path.join(slot_dir, "ConsistencyTier.txt"), p["consistency"]["tier"])

            self.set_status("Player slots generated.")
            messagebox.showinfo("Success", "Player slots generated into p0–p9.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate slots:\n{e}")
            self.set_status("Generate failed.")

        self.export_all_obs_files()

    def on_build_career_db(self):
        try:
            self.set_status("Building career database...")

            # Use the same file the rest of the tool reads
            output_path = os.path.join(BASE_DIR, "career_stats.json")

            build_career_database(output_path, current_season=self.current_season)

            self.set_status("Career database built successfully.")
            messagebox.showinfo("Success", "Career database has been built.")

        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to build career database:\n{e}")
            self.set_status("Career DB build failed.")
                
                
    def on_player_spotlight(self):
        if not self.current_match_players:
            messagebox.showerror("Error", "Please generate player slots first.")
            return

        export_dir = self.require_output_folder()
        if not export_dir:
            return

        # Prepare the list of players and names
        players = self.current_match_players
        names = [p["name"] for p in players]
        self.spotlight_idx = 0 

        # Load the career DB for Trend/Tag data
        career_path = os.path.join(BASE_DIR, "career_stats.json")
        with open(career_path, "r", encoding="utf-8") as f:
            db = json.load(f)

        win = tk.Toplevel(self.root)
        win.title("Spotlight Operator")
        win.geometry("500x700")

        ttk.Label(win, text="Active Spotlight Player:").pack(pady=5)
        
        # Dropdown selection
        combo_var = tk.StringVar()
        combo = ttk.Combobox(win, textvariable=combo_var, values=names, state="readonly")
        combo.pack(fill="x", padx=20)

        output = tk.Text(win, wrap="word", font=("Courier", 10), height=20)
        output.pack(expand=True, fill="both", padx=20, pady=10)

        def update_spotlight(idx):
            self.spotlight_idx = idx % len(players)
            p_match = players[self.spotlight_idx]
            selected_name = p_match["name"]
            combo_var.set(selected_name)

            # Get full career data. Priority: real career data > this
            # match player's own VERIFIED current-season stats (fetched
            # per-player during Generate Player Slots, real numbers, not
            # a guess) > genuinely nothing. Personal stats are NEVER
            # averaged from teammates — that's only ever done for the
            # 3 team-comparison graphics.
            cid = p_match.get("canonical")
            career_player_data = db["players"].get(cid)
            has_real_career = bool(career_player_data and career_player_data.get("career"))

            kills = p_match.get("kills", 0) or 0
            deaths = p_match.get("deaths", 0) or 0
            has_verified_season = bool(
                p_match.get("_verified_season_stats")
                and (kills or deaths or p_match.get("damage"))
            )

            if has_real_career:
                player_data = dict(career_player_data)
                is_new_player = False
                is_season_only = False
            elif has_verified_season:
                player_data = dict(career_player_data) if career_player_data else {}
                player_data["career"] = {
                    "kills": kills,
                    "deaths": deaths,
                    "damage": p_match.get("damage", 0) or 0,
                    "maps": p_match.get("maps", 0) or 0,
                    "KD": (kills / deaths) if deaths > 0 else kills,
                    "score": p_match.get("score", 0) or 0,
                }
                # Generate Player Slots already computed real, season-
                # based skill percentiles for this player (the fallback
                # system, ranked against the actual league distribution)
                # — they're sitting right here on p_match. Without
                # copying them over, the Skill Profile radar/bars read
                # an empty dict and show a flat 0% for everything, even
                # though real numbers exist.
                for tag in ("slayer", "sharpshooter", "consistency", "clutch", "anchor", "breaker"):
                    tag_data = p_match.get(tag)
                    if tag_data:
                        player_data[tag] = tag_data
                is_new_player = False
                is_season_only = True
            else:
                player_data = {}
                is_new_player = True
                is_season_only = False

            player_data["name"] = selected_name
            player_data["stats_estimated"] = False
            player_data["is_season_only"] = is_season_only

            # Determine Side
            team_b_names = [self.team_b_listbox.get(i) for i in range(self.team_b_listbox.size())]
            side = "Red" if selected_name in team_b_names else "Blue"

            # Generate 4K PNG
            from utils.graphics_engine import generate_player_card
            try:
                generate_player_card(player_data, team_side=side, export_dir=export_dir)
                self.set_status(f"Updated 4K Graphic: {selected_name}")

                # Thin HTML wrapper around the PNG so it can sit in OBS
                # as a Browser Source (auto-refreshing, like the other
                # three graphics) instead of needing a screen-capture
                # workaround.
                from analysis.html_export import render_spotlight_html
                spotlight_html = render_spotlight_html("spotlight_card.png")
                with open(os.path.join(export_dir, "spotlight.html"), "w", encoding="utf-8") as f:
                    f.write(spotlight_html)
            except Exception as e:
                print(f"Graphics Error: {e}")
                messagebox.showerror("Graphics Error", str(e))

            # Update Text Preview
            text = f"PLAYER: {selected_name}\n"
            text += f"Team:   {p_match.get('team', 'Unknown')}\n"
            text += f"Side:   {side}\n"
            text += "-"*30 + "\n"
            if is_new_player:
                text += f"🆕 NEW PLAYER — Season {self.current_season}\n"
                text += "No career stats recorded yet for this player.\n"
                text += "(Not shown as an estimate or average — personal\n"
                text += "stats stay untouched until they actually play.)\n"
            else:
                career = player_data.get("career", {})
                if is_season_only:
                    text += f"🆕 NEW THIS SEASON — no prior-season history on file\n"
                    text += f"(numbers below are real Season {self.current_season} stats)\n\n"
                text += f"Kills:  {int(career.get('kills',0)):,}\n"
                text += f"Maps:   {int(career.get('maps',0))}\n"
                text += f"KD:     {career.get('KD',0):.2f}\n\n"
                text += "SKILL PERCENTILES" + (" (this season only):\n" if is_season_only else ":\n")
                for tag in ["slayer", "sharpshooter", "consistency", "clutch", "anchor"]:
                    t_obj = player_data.get(tag, {})
                    pct = t_obj.get('pct')
                    pct_str = f"{pct:.0f}%" if pct is not None else "N/A"
                    text += f"{tag.title():<14}: {pct_str}\n"

            output.delete("1.0", tk.END)
            output.insert(tk.END, text)

        # Button logic
        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="<< Prev", 
                   command=lambda: update_spotlight(self.spotlight_idx - 1)).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="Next >>", 
                   command=lambda: update_spotlight(self.spotlight_idx + 1)).grid(row=0, column=1, padx=5)

        # Sync dropdown selection to buttons
        combo.bind("<<ComboboxSelected>>", lambda e: update_spotlight(names.index(combo.get())))

        # Initialize first player
        update_spotlight(0)

    def on_team_identity(self):
        team = self.team_a_var.get()
        if not team:
            messagebox.showerror("Error", "Select a team first.")
            return

        team_players = [p for p in self.current_match_players if p.get("team") == team]

        if len(team_players) == 0:
            messagebox.showerror("Error", "No players selected for this team.")
            return

        identity_data = generate_team_identity_block(team_players, team, self.map_var.get())
        identity_text = format_team_identity(identity_data)

        win = tk.Toplevel(self.root)
        win.title(f"Team Identity — {team}")
        win.geometry("500x600")

        output = tk.Text(win, wrap="word")
        output.pack(expand=True, fill="both", padx=10, pady=10)
        output.insert(tk.END, identity_text)
        output.config(state="disabled")

        ttk.Label(
            win,
            text="This is included in the matchup.html auto-exported by Generate Player Slots.",
            foreground="#666666",
        ).pack(pady=(0, 10))
  
        
    def generate_player_tags(self, player_entry, map_type):
        tags_out = []

        # ---------------------------------------------------------
        # Slayer (career)
        # ---------------------------------------------------------
        slayer = player_entry.get("slayer", {})
        slayer_strength = slayer.get("strength") or player_entry.get("slayer_strength")
        if isinstance(slayer_strength, str):
            tags_out.append(slayer_strength)

        # ---------------------------------------------------------
        # Consistency (career - hybrid system)
        # ---------------------------------------------------------
        consistency = player_entry.get("consistency", {})
        if isinstance(consistency, dict):
            score = consistency.get("raw")
            if isinstance(score, (int, float)):
                tags_out.append(f"Cons {score:.2f}")

        # ---------------------------------------------------------
        # Payload Objective Specialist (match-based)
        # ---------------------------------------------------------
        if map_type == "Payload":
            pl_info = player_entry.get("objective_payload_components", {})
            pl_score = pl_info.get("payload_score_raw", 0.0)
            tags_out.append(f"ObjPL {pl_score:.2f}")

        # ---------------------------------------------------------
        # Domination Objective Specialist (match-based)
        # ---------------------------------------------------------
        if map_type == "Domination":
            dom_info = player_entry.get("objective_domination", {})
            dom_score = dom_info.get("raw", 0.0)
            tags_out.append(f"ObjDOM {dom_score:.2f}")

        # ---------------------------------------------------------
        # Sharpshooter (career)
        # ---------------------------------------------------------
        sharp = player_entry.get("sharpshooter", {}).get("score") or player_entry.get("sharpshooter_score")
        if isinstance(sharp, (int, float)):
            tags_out.append(f"Sharp {sharp:.2f}")

        return ", ".join(tags_out)
        

    def on_match_storyline(self):
        team_a = self.team_a_var.get()
        team_b = self.team_b_var.get()

        if not team_a or not team_b:
            messagebox.showerror("Error", "Select both Team A and Team B.")
            return

        if not self.current_match_players:
            messagebox.showerror("Error", "Generate Player Slots first.")
            return

        # ---------------------------------------------------------
        # Use the already-selected, already-enriched match players
        # directly (same source get_team_roster_data / OBS export use)
        # instead of re-looking them up in self.stats_by_id. That
        # lookup silently dropped any player without live synced stats
        # yet — e.g. a player just moved onto this team via Manage
        # Roster who hasn't played a match under it yet — which could
        # empty out a team's list even though players were clearly
        # selected in the GUI.
        # ---------------------------------------------------------
        teamA_players = [p for p in self.current_match_players if p.get("team") == team_a]
        teamB_players = [p for p in self.current_match_players if p.get("team") == team_b]

        if not teamA_players or not teamB_players:
            messagebox.showerror("Error", "No players selected for one or both teams.")
            return

        # ---------------------------------------------------------
        # Generate storyline + identity blocks
        # ---------------------------------------------------------
        map_type = self.map_var.get()
        storyline_text = matchup_storyline(teamA_players, teamB_players, map_type)

        identity_data_a = generate_team_identity_block(teamA_players, team_a, map_type)
        identity_text_a = format_team_identity(identity_data_a)

        identity_data_b = generate_team_identity_block(teamB_players, team_b, map_type)
        identity_text_b = format_team_identity(identity_data_b)

        full_story = (
            storyline_text
            + "\n\nTEAM IDENTITY SUMMARY – " + team_a + "\n"
            + identity_text_a
            + "\n\nTEAM IDENTITY SUMMARY – " + team_b + "\n"
            + identity_text_b
        )

        # ---------------------------------------------------------
        # Popup window (preview only — export now happens
        # automatically from Generate Player Slots as a pretty HTML
        # file, so there's no separate export button here anymore)
        # ---------------------------------------------------------
        win = tk.Toplevel(self.root)
        win.title("Match Storyline")
        win.geometry("600x700")

        output = tk.Text(win, wrap="word")
        output.pack(expand=True, fill="both", padx=10, pady=10)
        output.insert(tk.END, full_story)
        output.config(state="disabled")

        ttk.Label(
            win,
            text="This is auto-exported as matchup.html whenever you click Generate Player Slots.",
            foreground="#666666",
        ).pack(pady=(0, 10))
    
    
    def compute_ranking_data(self, tag):
        """
        Shared computation used by both the on-screen Rankings popup and
        the auto-exported HTML ranking pages, so they can never disagree.
        Returns None if teams aren't selected, or a dict with
        empty=True if there's no ranked data for this tag.

        NOTE: this deliberately does NOT re-attach career tags from
        match_engine.load_career_db() (final_db.json) — that's a stale,
        separate legacy file from career_stats.json, and re-attaching
        from it here was silently clobbering the correct consistency/
        anchor/clutch/breaker values that on_generate_slots already
        attached from career_stats.json. self.current_match_players is
        already fully enriched by the time this runs.
        """
        team_a = self.team_a_var.get()
        team_b = self.team_b_var.get()
        if not team_a or not team_b:
            return None

        if tag == "Slayer":
            ranked = rank_match_players_slayer(self.current_match_players)
        elif tag == "Sharpshooter":
            ranked = rank_match_players_sharpshooter(self.current_match_players)
        elif tag == "Payload Objective Specialist":
            ranked = rank_match_players_objpl(self.current_match_players)
        elif tag == "Domination Objective Specialist":
            ranked = rank_match_players_objdom(self.current_match_players)
        elif tag == "Consistency":
            ranked = rank_match_players_by_tag(self.current_match_players, "consistency")
        elif tag == "Clutch":
            ranked = rank_match_players_clutch(self.current_match_players)
        elif tag == "Anchor":
            ranked = rank_match_players_by_tag(self.current_match_players, "anchor")
        elif tag == "Breaker":
            ranked = rank_match_players_by_tag(self.current_match_players, "breaker")
        else:
            return None

        if not ranked:
            return {"empty": True, "tag": tag, "team_a": team_a, "team_b": team_b}

        left, right = split_two_columns(ranked, team_a, team_b)

        # Only average players who actually HAVE real data for this tag.
        # A player with no career data (e.g. missing from the local
        # match-history cache) previously defaulted to a raw score of
        # 0.0, silently counted as if they'd genuinely earned the worst
        # possible score — dragging their team's average, and therefore
        # the win prediction, down as if they were a real liability
        # rather than simply unmeasured.
        left_scored = [p for p in left if p.get("has_data", True)]
        right_scored = [p for p in right if p.get("has_data", True)]
        missing_left = len(left) - len(left_scored)
        missing_right = len(right) - len(right_scored)

        teamA_total = sum(p["score_raw"] for p in left_scored)
        teamB_total = sum(p["score_raw"] for p in right_scored)
        teamA_avg = teamA_total / max(1, len(left_scored))
        teamB_avg = teamB_total / max(1, len(right_scored))

        delta = teamB_avg - teamA_avg
        if delta > 0:
            fav_delta = team_b
        elif delta < 0:
            fav_delta = team_a
        else:
            fav_delta = "Neither team"
        delta_mag = abs(delta)
        stronger_avg = max(teamA_avg, teamB_avg)
        rel_adv = (delta_mag / stronger_avg * 100) if stronger_avg > 0 else 0.0

        if tag == "Slayer":
            pred = compute_slayer_prediction(left_scored, right_scored)
            teamA_win = pred["teamA_win"]
            teamB_win = pred["teamB_win"]
        else:
            if max(teamA_avg, teamB_avg) == 0:
                edge = 0
            else:
                edge = (teamB_avg - teamA_avg) / max(teamA_avg, teamB_avg)
            k = 1.1
            pB = 1 / (1 + math.exp(-k * edge))
            pA = 1 - pB
            teamA_win = round(pA * 100)
            teamB_win = round(pB * 100)

        swing = abs(teamA_win - teamB_win)
        fav = team_a if teamA_win > teamB_win else team_b

        return {
            "empty": False,
            "tag": tag,
            "left": left,
            "right": right,
            "team_a": team_a,
            "team_b": team_b,
            "teamA_total": teamA_total,
            "teamB_total": teamB_total,
            "teamA_avg": teamA_avg,
            "teamB_avg": teamB_avg,
            "missing_left": missing_left,
            "missing_right": missing_right,
            "delta_mag": delta_mag,
            "fav_delta": fav_delta,
            "rel_adv": rel_adv,
            "teamA_win": teamA_win,
            "teamB_win": teamB_win,
            "swing": swing,
            "fav": fav,
        }

    def on_rankings(self):
        if not self.current_match_players:
            messagebox.showerror("Error", "Generate player slots first.")
            return

        win = tk.Toplevel(self.root)
        win.title("Rankings")
        win.geometry("800x600")

        tags = RANKING_TAGS

        ttk.Label(win, text="Select Tag:").pack(anchor="w", padx=10, pady=5)
        combo = ttk.Combobox(win, values=tags, state="readonly")
        combo.pack(fill="x", padx=10)

        output = tk.Text(win, wrap="word")
        output.pack(expand=True, fill="both", padx=10, pady=10)

        def show():
            tag = combo.get()
            if not tag:
                return

            data = self.compute_ranking_data(tag)
            if data is None:
                messagebox.showerror("Error", "Select both teams first.")
                return

            if data.get("empty"):
                output.delete("1.0", tk.END)
                output.insert(tk.END, "No data available for this tag.")
                return

            team_a = data["team_a"]
            team_b = data["team_b"]
            left = data["left"]
            right = data["right"]

            text = f"TOP {tag.upper()} PLAYERS (THIS MATCH):\n\n"

            # Two-column layout, but keep global rank
            max_rows = max(len(left), len(right))
            text += f"{team_a:<24}{team_b}\n"
            text += "-" * 48 + "\n"

            for i in range(max_rows):
                left_str = ""
                right_str = ""

                if i < len(left):
                    lp = left[i]
                    pct = lp.get("pct")
                    if pct is not None:
                        pct_str = f"{pct:.0f}%"
                        left_str = f"{lp['rank']:>2}. {lp['name']:<16} {lp['score_display']:>6} ({pct_str})"
                    else:
                        left_str = f"{lp['rank']:>2}. {lp['name']:<16} {lp['score_display']:>6}"

                if i < len(right):
                    rp = right[i]
                    pct = rp.get("pct")
                    if pct is not None:
                        pct_str = f"{pct:.0f}%"
                        right_str = f"{rp['rank']:>2}. {rp['name']:<16} {rp['score_display']:>6} ({pct_str})"
                    else:
                        right_str = f"{rp['rank']:>2}. {rp['name']:<16} {rp['score_display']:>6}"

                text += f"{left_str:<24}{right_str}\n"

            text += "-" * 48 + "\n"
            text += f"{team_a} Total: {data['teamA_total']:.2f}".ljust(24)
            text += f"{team_b} Total: {data['teamB_total']:.2f}\n"

            text += f"{team_a} Avg:   {data['teamA_avg']:.2f}".ljust(24)
            text += f"{team_b} Avg:   {data['teamB_avg']:.2f}\n"

            text += f"Delta: {data['delta_mag']:.2f} in favour of {data['fav_delta']}\n"
            text += f"Relative Advantage: {data['rel_adv']:.1f}%\n"

            text += f"Win Chance: {team_a} {data['teamA_win']}% — {team_b} {data['teamB_win']}%\n"
            text += f"Win Swing:  {data['swing']}% in favour of {data['fav']}\n"

            text += "\n" + "\n".join(RANKING_FORMULAS.get(tag, [])) + "\n"

            output.delete("1.0", tk.END)
            output.insert(tk.END, text)

        ttk.Button(win, text="Show Rankings", command=show).pack(pady=5)
        ttk.Label(
            win,
            text="All 8 tags are auto-exported as HTML whenever you click Generate Player Slots.",
            foreground="#666666",
        ).pack(pady=(0, 5))
   

    # dashleague_cast_tool.py -> on_rookie_leaderboard()

    def on_rookie_leaderboard(self):
        from analysis.rookie_leaderboard import rank_rookies_by_tag, ROOKIE_KILL_THRESHOLD
        season = self.current_season
        tag = "slayer" 
        
        rookies = rank_rookies_by_tag(season, tag)

        # 1. Text display for the GUI window
        lines = []
        lines.append(f"ROOKIE LEADERBOARD — Season {season}")
        lines.append(f"Rookie = under {ROOKIE_KILL_THRESHOLD:,} career kills, regardless of seasons played.")
        lines.append("")
        lines.append(f"{'Rank':<5} {'Name':<18} {'Team':<12} {'Score':<10} {'KD':<6} {'Maps':<6} {'Kills':<8}")
        lines.append("-" * 75)

        for r in rookies:
            score_str = f"{int(r['score']):,}" 
            kd_str = f"{r['kd']:.2f}"
            maps_str = f"{int(r['maps'])}"
            kills_str = f"{int(r['kills'])}"
            lines.append(f"{r['rank']:<5} {r['name']:<18} {r['team']:<12} {score_str:<10} {kd_str:<6} {maps_str:<6} {kills_str:<8}")

        text = "\n".join(lines)

        win = tk.Toplevel(self.root)
        win.title("Rookie Standings")
        win.geometry("800x600")

        output = tk.Text(win, wrap="none", font=("Courier", 10))
        output.pack(expand=True, fill="both", padx=10, pady=10)
        output.insert(tk.END, text)
        output.config(state="disabled")

        def export_html():
            from analysis.html_export import render_rookie_leaderboard_html
            html_content = render_rookie_leaderboard_html(rookies, season, ROOKIE_KILL_THRESHOLD)
            html_path = os.path.join(OBS_EXPORT_DIR, "rookie_leaderboard.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            self.set_status("Exported Rookie HTML")
            messagebox.showinfo("Exported", f"HTML updated\nLocation: {html_path}")

        ttk.Button(win, text="Export HTML for OBS Browser Source", command=export_html).pack(pady=10)
        ttk.Label(
            win,
            text="Also auto-refreshed whenever you click Generate Player Slots.",
            foreground="#666666",
        ).pack(pady=(0, 10))

        
    def export_all_obs_files(self):
        """
        Unified export function that writes all OBS text files
        based on the current map type and current match players.
        """

        map_type = self.map_var.get()
        team_a = self.team_a_var.get()
        team_b = self.team_b_var.get()

        if not map_type or not team_a or not team_b:
            return

        # --- Extract selected players for each team ---
        teamA_players = [p for p in self.current_match_players if p.get("team") == team_a]
        teamB_players = [p for p in self.current_match_players if p.get("team") == team_b]

        if len(teamA_players) == 0 or len(teamB_players) == 0:
            print("OBS export skipped: no selected players for one or both teams.")
            return

        # Define names for identity block
        teamA_name = team_a
        teamB_name = team_b

        # --- STORYLINE + TEAM IDENTITY (pretty HTML, replaces storyline.txt) ---
        try:
            narrative_text = matchup_narrative(teamA_players, teamB_players, map_type)

            identity_data_a = generate_team_identity_block(teamA_players, teamA_name, map_type)
            identity_data_b = generate_team_identity_block(teamB_players, teamB_name, map_type)

            from analysis.html_export import render_matchup_html
            tiers = self.config.get("tiers", {})
            matchup_html = render_matchup_html(
                narrative_text,
                identity_data_a,
                identity_data_b,
                teamA_name,
                teamB_name,
                season=self.current_season,
                tier_a=tiers.get(teamA_name),
                tier_b=tiers.get(teamB_name),
            )
            with open(os.path.join(OBS_EXPORT_DIR, "matchup.html"), "w", encoding="utf-8") as f:
                f.write(matchup_html)

        except Exception as e:
            print("Storyline export failed:", e)

        # --- RANKING PAGES (7 tags relevant to the current map mode —
        #     Payload Objective is skipped in Domination matches and
        #     vice versa, since that data isn't relevant either way) ---
        try:
            from analysis.html_export import render_ranking_html
            tiers = self.config.get("tiers", {})
            for tag in RANKING_TAGS:
                if tag == "Payload Objective Specialist" and map_type != "Payload":
                    continue
                if tag == "Domination Objective Specialist" and map_type != "Domination":
                    continue
                data = self.compute_ranking_data(tag)
                if not data or data.get("empty"):
                    continue
                ranking_html = render_ranking_html(
                    tag,
                    data,
                    RANKING_FORMULAS.get(tag, []),
                    season=self.current_season,
                    tier_a=tiers.get(teamA_name),
                    tier_b=tiers.get(teamB_name),
                )
                slug = RANKING_TAG_SLUGS.get(tag, tag.lower())
                with open(os.path.join(OBS_EXPORT_DIR, f"rankings_{slug}.html"), "w", encoding="utf-8") as f:
                    f.write(ranking_html)
        except Exception as e:
            print("Rankings export failed:", e)

        # --- ROOKIE LEADERBOARD (season-wide, refreshed here for
        #     convenience so it's always current before a broadcast) ---
        try:
            from analysis.rookie_leaderboard import rank_rookies_by_tag, ROOKIE_KILL_THRESHOLD
            from analysis.html_export import render_rookie_leaderboard_html
            rookies = rank_rookies_by_tag(self.current_season, "slayer")
            rookie_html = render_rookie_leaderboard_html(rookies, self.current_season, ROOKIE_KILL_THRESHOLD)
            with open(os.path.join(OBS_EXPORT_DIR, "rookie_leaderboard.html"), "w", encoding="utf-8") as f:
                f.write(rookie_html)
        except Exception as e:
            print("Rookie leaderboard export failed:", e)

        # --- TALE OF THE TAPE / TEAM DNA / WIN PROBABILITY (4K PNGs +
        #     HTML wrappers). These used to require manually clicking
        #     their own buttons every time; since every cast uses all
        #     three anyway, they now regenerate automatically alongside
        #     everything else whenever the team composition changes. The
        #     buttons still exist too, for a one-off manual refresh if
        #     ever needed without touching team selection. ---
        try:
            from utils.graphics_engine import (
                generate_tale_of_the_tape,
                generate_team_dna,
                generate_win_probability,
            )
            from analysis.html_export import render_spotlight_html

            roster_a = self.get_team_roster_data(teamA_name)
            roster_b = self.get_team_roster_data(teamB_name)

            generate_tale_of_the_tape(roster_a, roster_b, teamA_name, teamB_name, export_dir=OBS_EXPORT_DIR)
            with open(os.path.join(OBS_EXPORT_DIR, "tale_of_the_tape.html"), "w", encoding="utf-8") as f:
                f.write(render_spotlight_html("tale_of_the_tape.png"))

            generate_team_dna(roster_a, roster_b, teamA_name, teamB_name, export_dir=OBS_EXPORT_DIR)
            with open(os.path.join(OBS_EXPORT_DIR, "team_dna.html"), "w", encoding="utf-8") as f:
                f.write(render_spotlight_html("team_dna.png"))

            generate_win_probability(roster_a, roster_b, teamA_name, teamB_name, export_dir=OBS_EXPORT_DIR)
            with open(os.path.join(OBS_EXPORT_DIR, "win_probability.html"), "w", encoding="utf-8") as f:
                f.write(render_spotlight_html("win_probability.png"))
        except Exception as e:
            print("Comparison graphics export failed:", e)

        # --- PREDICTIONS ---
        try:
            if hasattr(self, "generate_predictions"):
                predictions = self.generate_predictions(teamA_players, teamB_players)
                write_text(os.path.join(OBS_EXPORT_DIR, "predictions.txt"), predictions)
        except Exception as e:
            print("Prediction export failed:", e)

         # --- PLAYER TAG EXPORTS ---
        try:
            for idx, p in enumerate(self.current_match_players):
                # p IS the enriched match player object
                tags_text = self.generate_player_tags(p, map_type)

                slot_path = os.path.join(PLAYERS_DIR, f"p{idx}", "Tags.txt")
                write_text(slot_path, tags_text)

        except Exception as e:
            print("Tag export failed:", e)

        print(f"OBS files updated for {map_type}")

    def refresh_output_dirs(self):
        global STATS_DIR, PLAYERS_DIR, OBS_EXPORT_DIR
        STATS_DIR = self.output_root
        PLAYERS_DIR = os.path.join(STATS_DIR, "players")
        OBS_EXPORT_DIR = os.path.join(STATS_DIR, "obs_exports")
        os.makedirs(PLAYERS_DIR, exist_ok=True)
        os.makedirs(OBS_EXPORT_DIR, exist_ok=True)

    def choose_output_folder(self):
        folder = filedialog.askdirectory(title="Select output folder for OBS + players")
        if not folder:
            return

        self.output_root = os.path.abspath(folder)
        config["output_root"] = self.output_root

        self.refresh_output_dirs()
        self.start_local_obs_server()

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

        messagebox.showinfo(
            "Output Folder Set",
            f"Output folder set to:\n{self.output_root}\n\n"
            "Point OBS to this folder for players and exports.\n\n"
            f"For HTML graphics, use http://localhost:{LOCAL_OBS_SERVER_PORT}/<filename> "
            "as the Browser Source URL instead of a local file path — "
            "that lets them auto-refresh when regenerated, no manual "
            "toggling needed."
        )

    def require_output_folder(self):
        """
        Returns the obs_exports subfolder of the configured output root,
        creating it if needed. If no output folder has been selected yet,
        warns the user and returns None so callers can abort.
        """
        if not getattr(self, "output_root", None):
            messagebox.showwarning(
                "Output Folder Not Set",
                "Please click 'Select Output Folder' before generating "
                "broadcast graphics, so exports know where to save."
            )
            return None

        export_dir = os.path.join(self.output_root, "obs_exports")
        os.makedirs(export_dir, exist_ok=True)
        return export_dir

    def open_roster_manager(self):
        """
        Lets a caster manually move a player onto a new team mid-season,
        before roster lock — e.g. a merge/disband where the player hasn't
        played a match under the new team yet, so match-derived team
        history hasn't caught up. Overrides are stored in
        roster_overrides.json and always take priority over history.
        """
        from analysis.player_identity_registry import PlayerIdentityRegistry
        pir = PlayerIdentityRegistry()

        win = tk.Toplevel(self.root)
        win.title("Manage Roster & Player Names")
        win.geometry("560x660")

        ttk.Label(win, text="Search player:").pack(anchor="w", padx=10, pady=(10, 0))
        search_var = tk.StringVar()
        search_entry = ttk.Entry(win, textvariable=search_var)
        search_entry.pack(fill="x", padx=10)

        list_frame = ttk.Frame(win)
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        roster_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        roster_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=roster_listbox.yview)

        # cid list kept in sync (index-aligned) with roster_listbox rows
        row_cids = []

        def refresh_list():
            pir.data = PlayerIdentityRegistry().data  # reload from disk
            overrides = load_roster_overrides()
            query = search_var.get().strip().lower()

            rows = []
            for cid, entry in pir.data.get("canonical", {}).items():
                names = entry.get("names") or []
                display_name = names[-1] if names else cid
                if query and query not in display_name.lower():
                    continue
                current_team = get_current_team(cid, pir, overrides) or "(no team)"
                overridden = " [MANUAL]" if cid in overrides else ""
                rows.append((display_name, cid, current_team, overridden))

            rows.sort(key=lambda r: r[0].lower())

            roster_listbox.delete(0, tk.END)
            row_cids.clear()
            for display_name, cid, current_team, overridden in rows:
                roster_listbox.insert(tk.END, f"{display_name}  \u2014  {current_team}{overridden}")
                row_cids.append(cid)

        search_entry.bind("<KeyRelease>", lambda e: refresh_list())

        assign_frame = ttk.Frame(win)
        assign_frame.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Label(assign_frame, text="Move selected player to:").grid(row=0, column=0, sticky="w")
        team_var = tk.StringVar()
        team_combo = ttk.Combobox(assign_frame, textvariable=team_var, values=self.config.get("teams", []))
        team_combo.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        assign_frame.columnconfigure(0, weight=1)

        rename_frame = ttk.Frame(win)
        rename_frame.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Label(rename_frame, text="Rename selected player to (their player ID stays the same):").grid(row=0, column=0, sticky="w")
        rename_var = tk.StringVar()
        rename_entry = ttk.Entry(rename_frame, textvariable=rename_var)
        rename_entry.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        rename_frame.columnconfigure(0, weight=1)

        def get_selected_cid():
            sel = roster_listbox.curselection()
            if not sel:
                messagebox.showwarning("No Selection", "Select a player from the list first.")
                return None
            return row_cids[sel[0]]

        def do_assign():
            cid = get_selected_cid()
            if not cid:
                return
            new_team = team_var.get().strip()
            if not new_team:
                messagebox.showwarning("No Team", "Choose or type a team to assign.")
                return
            set_override(cid, new_team)
            refresh_list()
            # Immediately reflect the move in the main window if either
            # side currently has a team selected.
            if self.team_a_var.get():
                self.on_team_select("A")
            if self.team_b_var.get():
                self.on_team_select("B")

        def do_clear():
            cid = get_selected_cid()
            if not cid:
                return
            clear_override(cid)
            refresh_list()
            if self.team_a_var.get():
                self.on_team_select("A")
            if self.team_b_var.get():
                self.on_team_select("B")

        def do_rename():
            cid = get_selected_cid()
            if not cid:
                return
            new_name = rename_var.get().strip()
            if not new_name:
                messagebox.showwarning("No Name", "Type the player's new name.")
                return
            rename_player(cid, new_name)
            rename_var.set("")
            refresh_list()
            self.set_status(f"Renamed player to {new_name}")
            if self.team_a_var.get():
                self.on_team_select("A")
            if self.team_b_var.get():
                self.on_team_select("B")

        btn_row = ttk.Frame(win)
        btn_row.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btn_row, text="Assign to Team", command=do_assign).pack(side="left", padx=(0, 5))
        ttk.Button(btn_row, text="Clear Override (use match history)", command=do_clear).pack(side="left", padx=(0, 5))
        ttk.Button(btn_row, text="Rename Player", command=do_rename).pack(side="left", padx=(0, 5))
        ttk.Button(btn_row, text="Close", command=win.destroy).pack(side="right")

        refresh_list()
        
        
    def on_match_prediction(self):
        team_a = self.team_a_var.get()
        team_b = self.team_b_var.get()

        if not team_a or not team_b:
            messagebox.showerror("Error", "Select both Team A and Team B.")
            return

        teamA_players = [p for p in self.current_match_players if p.get("team") == team_a]
        teamB_players = [p for p in self.current_match_players if p.get("team") == team_b]

        if not teamA_players or not teamB_players:
            messagebox.showerror("Error", "No players selected for one or both teams.")
            return

        prediction_text = generate_prediction(teamA_players, teamB_players, team_a, team_b)

        win = tk.Toplevel(self.root)
        win.title("Match Prediction")
        win.geometry("600x600")

        output = tk.Text(win, wrap="word")
        output.pack(expand=True, fill="both", padx=10, pady=10)
        output.insert(tk.END, prediction_text)

        def export():
            content = output.get("1.0", tk.END).strip()
            if not content:
                messagebox.showerror("Error", "No prediction text to export.")
                return
            path = export_to_obs("match_prediction.txt", content)
            messagebox.showinfo("Exported", f"Prediction exported to:\n{path}")

        ttk.Button(win, text="Export to OBS", command=export).pack(pady=5)
        
        
    def on_export_obs_all(self):
        team_a = self.team_a_var.get()
        team_b = self.team_b_var.get()

        if not team_a or not team_b:
            messagebox.showerror("Error", "Select both Team A and Team B.")
            return

        teamA_players = [p for p in self.current_match_players if p.get("team") == team_a]
        teamB_players = [p for p in self.current_match_players if p.get("team") == team_b]

        if not teamA_players or not teamB_players:
            messagebox.showerror("Error", "No players selected for one or both teams.")
            return

        output_folder = os.path.join(os.getcwd(), "obs_output")
        export_all_obs(output_folder, teamA_players, teamB_players, team_a, team_b)
        messagebox.showinfo("Exported", f"OBS files exported to:\n{output_folder}")    
         

def main():
    root = tk.Tk()
    app = DashLeagueGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()