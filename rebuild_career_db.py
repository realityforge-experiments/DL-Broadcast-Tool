import os
import json
from data.career_db import build_career_database
import sqlite3
from data.db_access import DB_PATH


conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
print("TABLES:", cur.fetchall())
conn.close()


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(BASE_DIR, "career_stats.json")

# Keep the identity registry's season tracking on the same scale the
# GUI uses (config.json's current_season), not the raw API CycleID
# scale, so recency checks elsewhere in the app stay reliable
# regardless of whether the DB was rebuilt from the GUI or this script.
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
current_season = None
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        current_season = json.load(f).get("current_season")

print("Rebuilding career database...")
ok = build_career_database(OUTPUT, current_season=current_season)

if ok:
    print("Career DB rebuilt successfully:", OUTPUT)
else:
    print("Career DB rebuild failed.")