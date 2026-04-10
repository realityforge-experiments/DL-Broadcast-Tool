import os
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

print("Rebuilding career database...")
ok = build_career_database(OUTPUT)

if ok:
    print("Career DB rebuilt successfully:", OUTPUT)
else:
    print("Career DB rebuild failed.")