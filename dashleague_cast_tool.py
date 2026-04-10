import os
import json
import math
from collections import defaultdict

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import requests

# --- Internal modules ---
from data.career_db import build_career_database
from rankings import top_players_by_tag
from analysis.team_identity_v2 import generate_team_identity_block
from analysis.storylines import generate_storyline, matchup_storyline
from analysis.predictions_v2 import generate_prediction
from analysis.obs_export_v2 import export_all_obs

from tags.objective_domination import (
    compute_dom_objective_for_career_player,
    compute_dom_objective_for_match_player,
    compute_dom_objective_team_scores,
)

from predictions.prediction_engine import generate_predictions

from match_engine import (
    rank_match_players_slayer,
    rank_match_players_objpl,
    rank_match_players_objdom,
    rank_match_players_sharpshooter,
    rank_match_players_clutch,
    split_two_columns,
    compute_slayer_prediction,
)

# ---------------------------------------------------------
#  PATHS + CONFIG
# ---------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

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

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        top_frame = ttk.Frame(main_frame)
        top_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        self.sync_button = ttk.Button(top_frame, text="Sync Stats", command=self.on_sync_stats)
        self.sync_button.grid(row=0, column=0, padx=(0, 10))

        self.build_db_button = ttk.Button(top_frame, text="Build Career Database", command=self.on_build_career_db)
        self.build_db_button.grid(row=0, column=1, padx=(0, 10))

        self.spotlight_button = ttk.Button(top_frame, text="Player Spotlight", command=self.on_player_spotlight)
        self.spotlight_button.grid(row=0, column=2, padx=(0, 10))

        self.team_id_button = ttk.Button(top_frame, text="Team Identity", command=self.on_team_identity)
        self.team_id_button.grid(row=0, column=3, padx=(0, 10))

        self.storyline_button = ttk.Button(top_frame, text="Match Storyline", command=self.on_match_storyline)
        self.storyline_button.grid(row=0, column=4, padx=(0, 10))

        self.rankings_button = ttk.Button(top_frame, text="Rankings", command=self.on_rankings)
        self.rankings_button.grid(row=0, column=5, padx=(0, 10))
        
        self.output_folder_button = ttk.Button(
            top_frame,
            text="Select Output Folder",
            command=self.choose_output_folder
        )
        self.output_folder_button.grid(row=0, column=6, padx=(0, 10))
        
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
            self.stats_by_id = {p["id"]: p for p in stats}
            self.set_status("Stats synced.")
            messagebox.showinfo("Success", f"Synced {len(stats)} player stats.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to sync stats:\n{e}")
            self.set_status("Sync failed.")
    
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
        team_players = [p for p in self.stats_by_id.values() if p.get("team") == team_name]

        if side == "A":
            self.team_a_players = team_players
            self.team_a_listbox.delete(0, tk.END)
            for p in team_players:
                self.team_a_listbox.insert(tk.END, p.get("name", "Unknown"))
        else:
            self.team_b_players = team_players
            self.team_b_listbox.delete(0, tk.END)
            for p in team_players:
                self.team_b_listbox.insert(tk.END, p.get("name", "Unknown"))
                
                
    def normalize_player(p):
        return {
            "id": p.get("PlayerUUID"),
            "name": p.get("PlayerGameName"),
            "team": p.get("TeamUUID"),
            "KD": p.get("KD", ""),
            "kills": p.get("Kills", ""),
            "deaths": p.get("Deaths", ""),
            "headshots": p.get("Headshots", ""),
            "accuracy": p.get("Accuracy", ""),
            "PAY_PushTime": p.get("PAY_PushTime", ""),
            "DOM_captures": p.get("DOM_Captures", ""),
            "DOM_counters": p.get("DOM_Counters", ""),
        }                
                
                

    def on_generate_slots(self):
        try:
            ensure_player_slots()

            # -----------------------------
            # 1. Collect selected players
            # -----------------------------
            selected_a = [self.team_a_players[i] for i in self.team_a_listbox.curselection()]
            selected_b = [self.team_b_players[i] for i in self.team_b_listbox.curselection()]

            if not selected_a:
                selected_a = self.team_a_players
            if not selected_b:
                selected_b = self.team_b_players

            # Sort and combine
            all_players = (
                sorted(selected_a, key=lambda x: x.get("name", "")) +
                sorted(selected_b, key=lambda x: x.get("name", ""))
            )

            # Limit to 10
            all_players = all_players[:10]

            # -----------------------------
            # 2. Normalize keys BEFORE attaching tags
            # -----------------------------
            for p in all_players:
                # Normalize stat keys to match DB/tag expectations
                p["CP_Captures"] = p.get("CP_captures", 0)
                p["DOM_Captures"] = p.get("DOM_captures", 0)
                p["DOM_Counters"] = p.get("DOM_counters", 0)

            # Save match players
            self.current_match_players = all_players

            # Debug
            if self.current_match_players:
                print("DEBUG MATCH PLAYER:", self.current_match_players[0])
            else:
                print("DEBUG MATCH PLAYER: EMPTY LIST")

            # -----------------------------
            # 3. Load career DB
            # -----------------------------
            career_path = os.path.join(BASE_DIR, "career_stats.json")
            career_db = None
            if os.path.exists(career_path):
                with open(career_path, "r", encoding="utf-8") as f:
                    career_db = json.load(f)

            # -----------------------------
            # 4. Attach modern career tags
            # -----------------------------
            if career_db is not None:
                for p in all_players:
                    pid = (
                        p.get("id")
                        or p.get("PlayerUUID")
                        or p.get("uuid")
                    )

                    if pid and pid in career_db["players"]:
                        pdata = career_db["players"][pid]

                        # Attach modern tags directly
                        p["slayer"] = pdata.get("slayer", {})
                        p["sharpshooter"] = pdata.get("sharpshooter", {})
                        p["objective_payload"] = pdata.get("objective_payload", {})
                        p["objective_domination"] = pdata.get("objective_domination", {})
                        p["consistency"] = pdata.get("consistency", {})
                        p["clutch"] = pdata.get("clutch", {})
                

            # -----------------------------
            # 5. Write OBS slot files
            # -----------------------------
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

                # Tag exports (use enriched match player dict)
                map_type = self.map_var.get()
                tags_text = self.generate_player_tags(p, map_type)
                write_text(os.path.join(slot_dir, "Tags.txt"), tags_text)

            self.set_status("Player slots generated.")
            messagebox.showinfo("Success", "Player slots generated into p0–p9.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate slots:\n{e}")
            self.set_status("Generate failed.")

        self.export_all_obs_files()

    def on_build_career_db(self):
        try:
            self.set_status("Building career database...")

            # Modernized output path
            output_path = os.path.join(BASE_DIR, "final_db.json")

            build_career_database(output_path)

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

            text = f"""PLAYER SPOTLIGHT — {name}

Slayer Tier: {slayer_strength}
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

        # Slayer
        slayer_strength = player_entry.get("slayer_strength")
        if slayer_strength:
            tags_out.append(slayer_strength)

        # Payload Objective Specialist (match-based)
        if map_type == "Payload":
            pl_info = player_entry.get("objective_payload_components", {})
            pl_score = pl_info.get("payload_score_raw", 0.0)
            tags_out.append(f"ObjPL {pl_score:.2f}")

        # Domination Objective Specialist (match-based)
        if map_type == "Domination":
            dom_info = player_entry.get("objective_domination_components", {})
            dom_score = dom_info.get("dom_score_raw", 0.0)
            tags_out.append(f"ObjDOM {dom_score:.2f}")

        # Sharpshooter
        sharp = player_entry.get("sharpshooter_score")
        if sharp is not None:
            tags_out.append(f"Sharp {sharp:.2f}")

        return ", ".join(tags_out)
        
        

    def on_match_storyline(self):
        team_a = self.team_a_var.get()
        team_b = self.team_b_var.get()

        if not team_a or not team_b:
            messagebox.showerror("Error", "Select both Team A and Team B.")
            return

        # Extract players for each team
        teamA_players = [self.stats_by_id[p["id"]] for p in self.current_match_players if p.get("team") == team_a]
        teamB_players = [self.stats_by_id[p["id"]] for p in self.current_match_players if p.get("team") == team_b]
        
        #print("TEAM A SAMPLE:", teamA_players[0])
        #print("TEAM B SAMPLE:", teamB_players[0])

        if not teamA_players or not teamB_players:
            messagebox.showerror("Error", "No players selected for one or both teams.")
            return

        # -----------------------------------------
        # 1. Generate storyline + identity block
        # -----------------------------------------
        storyline_text = matchup_storyline(teamA_players, teamB_players)

        # Team identity block (per team, using modern dict + formatter)
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

        # -----------------------------------------
        # 2. Popup window
        # -----------------------------------------
        win = tk.Toplevel(self.root)
        win.title("Match Storyline")
        win.geometry("600x700")

        output = tk.Text(win, wrap="word")
        output.pack(expand=True, fill="both", padx=10, pady=10)
        output.insert(tk.END, full_story)

        # -----------------------------------------
        # 3. Export to OBS
        # -----------------------------------------
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
        win.geometry("500x600")

        tags = [
            "Slayer",
            "Payload Objective Specialist",
            "Sharpshooter",
            "Domination Objective Specialist",
            "Consistency",
            "Clutch",
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

            elif tag == "Payload Objective Specialist":
                ranked = rank_match_players_objpl(self.current_match_players)

            elif tag == "Domination Objective Specialist":
                ranked = rank_match_players_objdom(self.current_match_players)
                
            elif tag == "Clutch":
                ranked = rank_match_players_clutch(self.current_match_players)               

            else:  # Sharpshooter
                ranked = rank_match_players_sharpshooter(self.current_match_players)

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
                    left_str = f"{lp['rank']:>2}. {lp['name']:<16} {lp['score_display']:>6}"

                if i < len(right):
                    rp = right[i]
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
                text += "\nConsistency Formula:\n"
                text += "Consistency = (Floor × 0.40) + (Stability × 0.40) + (Average Performance × 0.20)\n"
                text += "Where:\n"
                text += "- Per-Match Performance = (Slayer × 0.40) + (Objective × 0.40) + (Accuracy × 0.20)\n"
                text += "- Floor = the player's lowest per-match performance score\n"
                text += "- Stability = 1 / (1 + Adjusted Variance)\n"
                text += "- Adjusted Variance = Variance × (1 + 1 / Match Count)\n"
                
            elif tag == "Clutch":
                text += "\nClutch Formula:\n"
                text += "Clutch = (Pressure Efficiency × 0.40) + (Collapse Avoidance × 0.40) + (Conversion Rate × 0.20)\n"
                text += "Where:\n"
                text += "- Pressure Efficiency = Damage / (Deaths + 1)\n"
                text += "- Collapse Avoidance = Player's lowest per-map performance score\n"
                text += "- Conversion Rate = (Accuracy × 0.50) + (Headshot Rate × 0.50)\n"    

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
            career_path = os.path.join(BASE_DIR, "career_stats.json")
            if os.path.exists(career_path):
                with open(career_path, "r", encoding="utf-8") as f:
                    career_db = json.load(f)

                for idx, p in enumerate(self.current_match_players):
                    pid = p.get("id")
                    if pid and pid in career_db["players"]:
                        player_entry = career_db["players"][pid]
                        tags_text = self.generate_player_tags(player_entry, map_type)

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
                f"  - {tag.title()}: {data['tier']} Tier "
                f"(avg {data['avg_pct']:.1f} percentile)"
            )

        return "\n".join(lines)



    

def main():
    root = tk.Tk()
    app = DashLeagueGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()