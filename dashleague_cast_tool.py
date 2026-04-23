import os
import json
import math
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
from analysis.storylines import generate_storyline, matchup_storyline
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


def ensure_player_slots():
    os.makedirs(PLAYERS_DIR, exist_ok=True)
    for i in range(10):
        slot_dir = os.path.join(PLAYERS_DIR, f"p{i}")
        os.makedirs(slot_dir, exist_ok=True)


def write_text(path, value):
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(value))


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
       

    def load_config(self):
        if not os.path.exists(CONFIG_PATH):
            messagebox.showerror("Error", f"config.json not found at {CONFIG_PATH}")
            self.config = {}
            return
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self.current_season = self.config.get("current_season", 10)

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

        self.spotlight_button = ttk.Button(top_frame, text="Player Spotlight", command=self.on_player_spotlight)
        self.spotlight_button.grid(row=0, column=2, padx=(0, 10))

        self.team_id_button = ttk.Button(top_frame, text="Team Identity", command=self.on_team_identity)
        self.team_id_button.grid(row=0, column=3, padx=(0, 10))

        self.storyline_button = ttk.Button(top_frame, text="Match Storyline", command=self.on_match_storyline)
        self.storyline_button.grid(row=0, column=4, padx=(0, 10))

        self.rankings_button = ttk.Button(top_frame, text="Rankings", command=self.on_rankings)
        self.rankings_button.grid(row=0, column=5, padx=(0, 10))
        
        self.rookie_button = ttk.Button(top_frame, text="Rookie Leaderboard", command=self.on_rookie_leaderboard)
        self.rookie_button.grid(row=0, column=6, padx=(0, 10))
        
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

        status_frame = ttk.Frame(self.root)
        status_frame.grid(row=1, column=0, sticky="ew")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor="w")
        status_label.grid(row=0, column=0, sticky="ew")
        status_frame.columnconfigure(0, weight=1)

    def set_status(self, text):
        self.status_var.set(text)
        self.root.update_idletasks()

    def on_sync_stats(self):
        try:
            self.set_status(f"Syncing stats for season {self.current_season}...")
            url = f"{API_BASE}/stats?season={self.current_season}"
            data = fetch_json(url)
            stats = data.get("data", [])

            print("DEBUG: Checking raw API teams...")
            for p in stats:
                print("TEAM FIELD:", repr(p.get("team")))

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
                if not canonical:
                    continue

                # Ensure first_season is set if missing
                entry = pir.data["canonical"].get(canonical)
                #if entry is not None and entry.get("first_season") is None:
                #    entry["first_season"] = self.current_season

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

                pdata = players_db.get(canonical, {})
                
                
                # Store basic stats into career DB so rookies have real data
                pdata["kills"] = merged.get("kills", 0)
                pdata["deaths"] = merged.get("deaths", 0)
                pdata["damage"] = merged.get("damage", 0)
                pdata["shots"] = merged.get("shots", 0)
                pdata["shots_hit"] = merged.get("shots_hit", 0)

                # Score is inside match_stats
                ms = merged.get("match_stats", {})
                pdata["score"] = ms.get("score", 0)

                # KD
                if pdata["deaths"] > 0:
                    pdata["kd"] = pdata["kills"] / pdata["deaths"]
                else:
                    pdata["kd"] = pdata["kills"]
                
                # Keep seasons_played updated
                #if merged.get("seasons_played"):
                #    pdata["seasons_played"] = merged["seasons_played"]
                    
                pdata["seasons_played"] = merged.get("seasons_played")

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

            # ---------------------------------------------------------
            # Debug: show teams detected
            # ---------------------------------------------------------
            teams_in_api = sorted({p["team"] for p in new_stats_by_id.values()})
            print("TEAMS IN API:", teams_in_api)

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
        print("TEAM SELECT FIRED:", side, "team_name=", team_name)

        # Debug: show how many players match this team
        matching = []
        for p in self.stats_by_id.values():
            if p.get("team") == team_name or p.get("TeamUUID") == team_name:
                matching.append(p)

        print(f"DEBUG: Found {len(matching)} players for team {team_name}")
        for p in matching:
            print("   PLAYER:", p.get("name"), "| TEAM:", p.get("team"))

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
            
            print("=== DEBUG MATCH_STATS SAMPLE ===")
            print(all_players[0].get("match_stats", {}))

            # ---------------------------------------------------------
            # 2. Normalize stat keys BEFORE attaching tags
            # ---------------------------------------------------------

            for p in all_players:
                ms = p.get("match_stats", {})

                # CP
                p["CP_Captures"] = (
                    p.get("CP_Captures")
                    or p.get("CP_captures")
                    or ms.get("CP_Captures")
                    or ms.get("CP_captures")
                    or 0
                )

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
                # Resolve canonical ID first
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
            # 4. Compute match-based Breaker
            # ---------------------------------------------------------
            for p in all_players:
                breaker_raw = compute_breaker_for_match_player(p)
                p["breaker"] = {"raw": breaker_raw}

            # ---------------------------------------------------------
            # 5. Load career DB
            # ---------------------------------------------------------
            career_db = None
            career_path = os.path.join(BASE_DIR, "career_stats.json")
            if os.path.exists(career_path):
                with open(career_path, "r", encoding="utf-8") as f:
                    career_db = json.load(f)

            # ---------------------------------------------------------
            # 6. Compute match-based Consistency (raw only)
            # ---------------------------------------------------------
            
            print("\n=== DEBUG: Player objects BEFORE consistency ===")
            for p in all_players:
                print(p.get("name"), "| id:", p.get("id"), "| uuid:", p.get("uuid"), "| PlayerUUID:", p.get("PlayerUUID"), "| canonical:", p.get("canonical_id"))
                        
            
            
            consistency_rows = rank_match_players_consistency_career(all_players)
            consistency_map = {row["id"]: row["score_raw"] for row in consistency_rows}

            for p in all_players:
                raw = consistency_map.get(p["id"], 0.0)
                p["consistency"] = {"raw": raw}

            # ---------------------------------------------------------
            # 7. Build match-based consistency distribution
            # ---------------------------------------------------------
            consistency_distribution = [p["consistency"]["raw"] for p in all_players]

            # ---------------------------------------------------------
            # 8. Compute percentile + tier for match-based Consistency
            # ---------------------------------------------------------
            from data.tag_framework import percentile_rank, tier_from_percentile

            for p in all_players:
                raw = p["consistency"]["raw"]
                pct = percentile_rank(raw, consistency_distribution)
                tier = tier_from_percentile(pct)

                p["consistency"]["pct"] = pct
                p["consistency"]["tier"] = tier
                p["consistency"]["summary"] = f"{tier} Tier ({pct:.1f} percentile)"

            # ---------------------------------------------------------
            # 9. Attach career tags (DO NOT overwrite match consistency)
            # ---------------------------------------------------------
            if career_db is not None:
                for p in all_players:
                    cid = p.get("canonical")
                    if not cid:
                        continue

                    pdata = career_db["players"].get(cid)
                    if not pdata:
                        continue

                    p["slayer"] = pdata.get("slayer", {})
                    p["sharpshooter"] = pdata.get("sharpshooter", {})
                    p["objective_payload"] = pdata.get("objective_payload", {})
                    p["clutch"] = pdata.get("clutch", {})
                    p["anchor"] = pdata.get("anchor", {})
                    p["breaker"] = pdata.get("breaker", {})

                    # Do NOT overwrite match-based DomObj
                    if "objective_domination" not in p or not p["objective_domination"]:
                        p["objective_domination"] = pdata.get("objective_domination", {})

            # ---------------------------------------------------------
            # 10. Compute match-based Domination Objective
            # ---------------------------------------------------------
            for p in all_players:
                dom = compute_dom_objective_for_match_player(p)
                caps = dom.get("captures", 0)
                counters = dom.get("counters", 0)
                dom_score = caps * 0.4 + counters * 0.6

                print("DOM DEBUG:", p["name"], "caps=", caps, "counters=", counters)

                p["objective_domination"] = {
                    "raw": dom_score,
                    "pct": dom_score,      # <- match panel can now read this
                    "tier": "-",           # <- neutral tier for single-match view
                    "captures": caps,
                    "counters": counters,
                    "summary": "",         # optional, keeps shape consistent
                }

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

            build_career_database(output_path)
            #print("DEBUG CAREER DB KEYS:", career_db.keys())
            #print("DEBUG PLAYER COUNT:", len(career_db.get("players", {})))

            self.set_status("Career database built successfully.")
            messagebox.showinfo("Success", "Career database has been built.")

        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to build career database:\n{e}")
            self.set_status("Career DB build failed.")
                
                
    def on_player_spotlight(self):
        career_path = os.path.join(BASE_DIR, "career_stats.json")
        if not os.path.exists(career_path):
            messagebox.showerror("Error", "Build career database first.")
            return

        with open(career_path, "r", encoding="utf-8") as f:
            db = json.load(f)

        names = [p["name"] for p in db["players"].values()]
        names.sort()

        win = tk.Toplevel(self.root)
        win.title("Player Spotlight")
        win.geometry("400x500")

        ttk.Label(win, text="Select Player:").pack(anchor="w", padx=10, pady=5)
        combo = ttk.Combobox(win, values=names, state="readonly")
        combo.pack(fill="x", padx=10)

        output = tk.Text(win, wrap="word")
        output.pack(expand=True, fill="both", padx=10, pady=10)

        def show():
            name = combo.get()
            if not name:
                return

            player = next((p for p in db["players"].values() if p["name"] == name), None)
            if not player:
                output.delete("1.0", tk.END)
                output.insert(tk.END, "Player not found in career DB.")
                return

            career = player["career"]
            derived = player.get("derived", {})
            obj_pl = player.get("objective_payload_score")
            slayer_strength = player.get("slayer_strength", "Unknown")

            consistency = player.get("consistency", {})
            cons_tier = consistency.get("tier", "N/A")
            cons_pct = consistency.get("pct")
            cons_summary = consistency.get("summary", "No consistency data available.")

            if isinstance(cons_pct, (int, float)):
                cons_line = f"{cons_tier} Tier ({cons_pct:.1f} percentile)"
            else:
                cons_line = f"{cons_tier} Tier"

            text = f"""PLAYER SPOTLIGHT — {name}

Slayer Tier: {slayer_strength}
Consistency: {cons_line}
Payload Objective Specialist: {obj_pl if obj_pl is not None else "N/A"}

Career Stats:
KD: {career['KD']:.2f}
Accuracy: {career['accuracy']:.2f}
Kills: {career['kills']}
Deaths: {career['deaths']}
Maps Played: {career['maps']}

Derived Metrics:
Kills/Map: {derived.get('kills_per_map', 0):.2f}
Deaths/Map: {derived.get('deaths_per_map', 0):.2f}
PushTime/Season: {derived.get('push_time_per_season', 0):.2f}

Consistency Summary:
{cons_summary}
"""

            output.delete("1.0", tk.END)
            output.insert(tk.END, text)
        def export():
            content = output.get("1.0", tk.END).strip()
            if not content:
                messagebox.showerror("Error", "No spotlight text to export.")
                return
            path = export_to_obs("spotlight.txt", content)
            messagebox.showinfo("Exported", f"Spotlight exported to:\n{path}")

        ttk.Button(win, text="Show Spotlight", command=show).pack(pady=5)
        ttk.Button(win, text="Export to OBS", command=export).pack(pady=5)

    def on_team_identity(self):
        team = self.team_a_var.get()
        if not team:
            messagebox.showerror("Error", "Select a team first.")
            return

        team_players = [p for p in self.current_match_players if p.get("team") == team]

        if len(team_players) == 0:
            messagebox.showerror("Error", "No players selected for this team.")
            return

        identity_data = generate_team_identity_block(team_players, team)
        identity_text = format_team_identity(identity_data)

        win = tk.Toplevel(self.root)
        win.title(f"Team Identity — {team}")
        win.geometry("500x600")

        output = tk.Text(win, wrap="word")
        output.pack(expand=True, fill="both", padx=10, pady=10)
        output.insert(tk.END, identity_text)

        def export():
            content = output.get("1.0", tk.END).strip()
            if not content:
                messagebox.showerror("Error", "No team identity text to export.")
                return
            filename = f"team_identity_{team}.txt"
            path = export_to_obs(filename, content)
            messagebox.showinfo("Exported", f"Team identity exported to:\n{path}")

        ttk.Button(win, text="Export to OBS", command=export).pack(pady=5)
  
        
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
            dom_info = player_entry.get("objective_domination_components", {})
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

        # ---------------------------------------------------------
        # 1. Attach career tags to ALL match players (CRITICAL)
        # ---------------------------------------------------------
        from match_engine import load_career_db, attach_career_tags_to_match_player
        career_db = load_career_db()

        # self.stats_by_id keys ARE canonical IDs
        for cid, p in self.stats_by_id.items():
            if cid in career_db["players"]:
                attach_career_tags_to_match_player(p, career_db["players"][cid])

        # ---------------------------------------------------------
        # 2. Extract players for each team (using enriched objects)
        # ---------------------------------------------------------
        teamA_players = []
        teamB_players = []

        for p in self.current_match_players:
            cid = p.get("canonical")   # <-- correct key
            if not cid:
                continue

            enriched = self.stats_by_id.get(cid)
            if not enriched:
                continue

            if enriched.get("team") == team_a:
                teamA_players.append(enriched)
            elif enriched.get("team") == team_b:
                teamB_players.append(enriched)

        if not teamA_players or not teamB_players:
            messagebox.showerror("Error", "No players selected for one or both teams.")
            return

        # ---------------------------------------------------------
        # 3. Generate storyline + identity blocks
        # ---------------------------------------------------------
        storyline_text = matchup_storyline(teamA_players, teamB_players)

        identity_data_a = generate_team_identity_block(teamA_players, team_a)
        identity_text_a = format_team_identity(identity_data_a)

        identity_data_b = generate_team_identity_block(teamB_players, team_b)
        identity_text_b = format_team_identity(identity_data_b)

        full_story = (
            storyline_text
            + "\n\nTEAM IDENTITY SUMMARY – " + team_a + "\n"
            + identity_text_a
            + "\n\nTEAM IDENTITY SUMMARY – " + team_b + "\n"
            + identity_text_b
        )

        # ---------------------------------------------------------
        # 4. Popup window
        # ---------------------------------------------------------
        win = tk.Toplevel(self.root)
        win.title("Match Storyline")
        win.geometry("600x700")

        output = tk.Text(win, wrap="word")
        output.pack(expand=True, fill="both", padx=10, pady=10)
        output.insert(tk.END, full_story)

        # ---------------------------------------------------------
        # 5. Export to OBS
        # ---------------------------------------------------------
        def export():
            content = output.get("1.0", tk.END).strip()
            if not content:
                messagebox.showerror("Error", "No storyline text to export.")
                return

            teamA_name = self.team_a_var.get()
            teamB_name = self.team_b_var.get()

            export_all_obs(
                OBS_EXPORT_DIR,
                teamA_players,
                teamB_players,
                teamA_name,
                teamB_name,
            )

            messagebox.showinfo("Exported", f"OBS files exported to:\n{OBS_EXPORT_DIR}")

        ttk.Button(win, text="Export to OBS", command=export).pack(pady=5)
    
    
    def on_rankings(self):
        if not self.current_match_players:
            messagebox.showerror("Error", "Generate player slots first.")
            return

        win = tk.Toplevel(self.root)
        win.title("Rankings")
        win.geometry("800x600")

        tags = [
            "Slayer",
            "Payload Objective Specialist",
            "Sharpshooter",
            "Domination Objective Specialist",
            "Consistency",
            "Clutch",
            "Anchor",
            "Breaker",
        ]

        ttk.Label(win, text="Select Tag:").pack(anchor="w", padx=10, pady=5)
        combo = ttk.Combobox(win, values=tags, state="readonly")
        combo.pack(fill="x", padx=10)

        output = tk.Text(win, wrap="word")
        output.pack(expand=True, fill="both", padx=10, pady=10)

        def show():
            tag = combo.get()
            if not tag:
                return

            team_a = self.team_a_var.get()
            team_b = self.team_b_var.get()

            if not team_a or not team_b:
                messagebox.showerror("Error", "Select both teams first.")
                return

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
                
            elif tag == "Rookie":
                ranked = compute_rookie_leaderboard(career_db, tag="slayer")
                # convert rookie rows to the same format as other rankings    

            else:
                messagebox.showerror("Error", f"Unknown tag: {tag}")
                return

            if not ranked:
                output.delete("1.0", tk.END)
                output.insert(tk.END, "No data available for this tag.")
                return

            left, right = split_two_columns(ranked, team_a, team_b)

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
                    #print("DEBUG LP ROW:", lp)  # <--- add this
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

            # -----------------------------
            # TEAM TOTALS & AVERAGES (COLUMN FORMAT)
            # -----------------------------
            teamA_total = sum(p["score_raw"] for p in left)
            teamB_total = sum(p["score_raw"] for p in right)

            teamA_avg = teamA_total / max(1, len(left))
            teamB_avg = teamB_total / max(1, len(right))

            text += "-" * 48 + "\n"
            text += f"{team_a} Total: {teamA_total:.2f}".ljust(24)
            text += f"{team_b} Total: {teamB_total:.2f}\n"

            text += f"{team_a} Avg:   {teamA_avg:.2f}".ljust(24)
            text += f"{team_b} Avg:   {teamB_avg:.2f}\n"
            
            
            # -----------------------------
            # DELTA (relative strength)
            # -----------------------------
            delta = teamB_avg - teamA_avg
            if delta > 0:
                fav_delta = team_b
            elif delta < 0:
                fav_delta = team_a
            else:
                fav_delta = "Neither team"

            delta_mag = abs(delta)
            text += f"Delta: {delta_mag:.2f} in favour of {fav_delta}\n"
            
            stronger_avg = max(teamA_avg, teamB_avg)
            if stronger_avg > 0:
                rel_adv = (delta_mag / stronger_avg) * 100
            else:
                rel_adv = 0.0

            text += f"Relative Advantage: {rel_adv:.1f}%\n"

            # -----------------------------
            # WIN CHANCE + SWING
            # -----------------------------
            if tag == "Slayer":
                pred = compute_slayer_prediction(left, right)
                teamA_win = pred["teamA_win"]
                teamB_win = pred["teamB_win"]
            else:
                # ObjPL win factor (simple logistic)
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

            text += f"Win Chance: {team_a} {teamA_win}% — {team_b} {teamB_win}%\n"
            text += f"Win Swing:  {swing}% in favour of {fav}\n"
            
            # -----------------------------
            # FORMULA EXPLANATION
            # -----------------------------
            if tag == "Slayer":
                text += "\nSlayer Formula:\n"
                text += "Slayer Score = (Damage per Map × 0.40) + (Kills per Map × 0.40) + (KD × 0.20)\n"

            elif tag == "Sharpshooter":
                text += "\nSharpshooter Formula:\n"
                text += "Sharpshooter = (Accuracy × 0.40) + (Headshot Rate × 0.40) + (Damage per Shot × 0.20)\n"
                text += "Where:\n"
                text += "- Accuracy = Shots Hit / Shots Fired\n"
                text += "- Headshot Rate = Headshots / Shots Hit\n"
                text += "- Damage per Shot = Damage / Shots Fired\n"

            elif tag == "Payload Objective Specialist":
                text += "\nPayload Objective Formula:\n"
                text += "ObjPL = (Presence × 0.40) + (PushTime Normalized × 0.40) + (PSI × 0.20)\n"
                text += "Where:\n"
                text += "- Presence = Player PushTime / Team PushTime\n"
                text += "- PSI = Damage / (Deaths + 1) × 1 / sqrt(PushTime + 1)\n"

            elif tag == "Domination Objective Specialist":
                text += "\nDomination Objective Formula:\n"
                text += "ObjDOM = (CapRate × 0.40) + (CounterRate × 0.60)\n"
                text += "Where:\n"
                text += "- CapRate = log(1 + DOM_captures) / log(21)\n"
                text += "- CounterRate = log(1 + DOM_counters) / log(21)\n"
                text += "Counters are weighted more heavily because they prevent enemy scoring.\n"
                
            elif tag == "Consistency":
                text += "\nConsistency Formula (Hybrid Career Tag):\n"
                text += "Consistency = (Floor × 0.40) + (Stability × 0.40) + (Average Performance × 0.20)\n"
                text += "Where:\n"
                text += "- Floor = lowest per-match performance score\n"
                text += "- Stability = 1 / (1 + Adjusted Variance)\n"
                text += "- Adjusted Variance = Variance × (1 + 1 / Match Count)\n"
                text += "- Average Performance = mean per-match performance score\n"
                
            elif tag == "Clutch":
                text += "\nClutch Formula:\n"
                text += "Clutch = (Pressure Efficiency × 0.40) + (Collapse Avoidance × 0.40) + (Conversion Rate × 0.20)\n"
                text += "Where:\n"
                text += "- Pressure Efficiency = Damage / (Deaths + 1)\n"
                text += "- Collapse Avoidance = Player's lowest per-map performance score\n"
                text += "- Conversion Rate = (Accuracy × 0.50) + (Headshot Rate × 0.50)\n" 

            elif tag == "Anchor":
                text += "\nAnchor Formula:\n"
                text += "Anchor = (Survivability × 0.45) + (DefensivePresence × 0.30) + (Consistency × 0.25)\n"
                text += "Where:\n"
                text += "- Survivability = (LeagueAvgDeathsPerMap / PlayerDeathsPerMap), clamped to [0.25, 1.50] then normalized to 0–1\n"
                text += "- DefensivePresence = (DamagePerMap / LeagueAvgDamagePerMap), clamped to [0, 1.5] then normalized to 0–1\n"
                text += "- Consistency = normalized 0–1 stability score from the Consistency tag\n"
                text += "Survivability reflects how hard the player is to remove; Defensive Presence measures baseline contribution; Consistency rewards stable defensive performance.\n"    
                
            elif tag == "Breaker":
                text += "\nBreaker Formula:\n"
                text += "Breaker = (DamageNorm × 0.60) + (KillsNorm × 0.40)\n"
                text += "Where:\n"
                text += "- DamageNorm = Damage per map normalized against league average\n"
                text += "- KillsNorm = Kills per map normalized against league average\n"
                text += "Breaker measures disruptive offensive pressure through high damage output and aggressive fragging.\n"
                
                
                

            output.delete("1.0", tk.END)
            output.insert(tk.END, text)

        def export():
            content = output.get("1.0", tk.END).strip()
            if not content:
                messagebox.showerror("Error", "No rankings text to export.")
                return
            tag = combo.get() or "rankings"
            filename = f"rankings_{tag}.txt"
            path = export_to_obs(filename, content)
            messagebox.showinfo("Exported", f"Rankings exported to:\n{path}")

        ttk.Button(win, text="Show Rankings", command=show).pack(pady=5)
   

    def on_rookie_leaderboard(self):
        from analysis.rookie_leaderboard import rank_rookies_by_tag

        season = self.current_season
        tag = "slayer"   # default tag for rookie leaderboard

        rookies = rank_rookies_by_tag(season, tag)

        # Build text output
        lines = []
        lines.append(f"ROOKIE LEADERBOARD — {tag.upper()} — Season {season}")
        lines.append("")
        lines.append(f"{'Rank':<5} {'Name':<18} {'Team':<8} {'Tier':<6} {'Pct':<6} {'Raw':<6}")
        lines.append("-" * 60)

        for r in rookies:
            pct = f"{r['pct']:.0f}%" if r["pct"] is not None else "-"
            raw = f"{r['raw']:.2f}"
            lines.append(f"{r['rank']:<5} {r['name']:<18} {r['team']:<8} {r['tier']:<6} {pct:<6} {raw:<6}")

        text = "\n".join(lines)

        # Popup window
        win = tk.Toplevel(self.root)
        win.title("Rookie Leaderboard")
        win.geometry("600x500")

        output = tk.Text(win, wrap="word")
        output.pack(expand=True, fill="both", padx=10, pady=10)
        output.insert(tk.END, text)

        
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

        # --- STORYLINE + TEAM IDENTITY ---
        try:
            storyline_text = matchup_storyline(teamA_players, teamB_players)

            identity_data_a = generate_team_identity_block(teamA_players, teamA_name)
            identity_data_b = generate_team_identity_block(teamB_players, teamB_name)

            identity_text_a = format_team_identity(identity_data_a)
            identity_text_b = format_team_identity(identity_data_b)

            full_story = (
                storyline_text
                + f"\n\nTEAM IDENTITY SUMMARY — {teamA_name}\n"
                + identity_text_a
                + f"\n\nTEAM IDENTITY SUMMARY — {teamB_name}\n"
                + identity_text_b
            )

            write_text(os.path.join(OBS_EXPORT_DIR, "storyline.txt"), full_story)

        except Exception as e:
            print("Storyline export failed:", e)

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

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

        messagebox.showinfo(
            "Output Folder Set",
            f"Output folder set to:\n{self.output_root}\n\n"
            "Point OBS to this folder for players and exports."
        )
        
        
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