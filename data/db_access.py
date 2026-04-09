import sqlite3
import os
from collections import defaultdict

# Resolve BroadcastTool/ as base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(BASE_DIR, "data", "match_history.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def query(sql, params=()):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def query_one(sql, params=()):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def aggregate_rounds_into_matches(rows):
    matches = defaultdict(lambda: {
        "MatchID": None,
        "CycleID": None,
        "Kills": 0,
        "Deaths": 0,
        "Damage": 0,
        "Score": 0,
        "Headshots": 0,
        "Shots": 0,
        "ShotsHit": 0,
        "CTF_Captures": 0,
        "CTF_Returns": 0,
        "CP_Captures": 0,
        "PAY_PushTime": 0,
        "DOM_Captures": 0,
        "DOM_Counters": 0,
        "Rounds": 0
    })

    for r in rows:
        mid = r["MatchID"]
        m = matches[mid]

        m["MatchID"] = mid
        m["CycleID"] = r["CycleID"] if "CycleID" in r else None
        m["TeamUUID"] = r["TeamUUID"]
        m["TeamColorID"] = r["TeamColorID"]

        m["Kills"] += r["Kills"]
        m["Deaths"] += r["Deaths"]
        m["Damage"] += r["Damage"]
        m["Score"] += r["Score"]
        m["Headshots"] += r["Headshots"]
        m["Shots"] += r["Shots"]
        m["ShotsHit"] += r["ShotsHit"]
        m["CTF_Captures"] += r["CTF_Captures"]
        m["CTF_Returns"] += r["CTF_Returns"]
        m["CP_Captures"] += r["CP_Captures"]
        m["PAY_PushTime"] += r["PAY_PushTime"]
        m["DOM_Captures"] += r["DOM_Captures"]
        m["DOM_Counters"] += r["DOM_Counters"]

        m["Rounds"] += 1

    return list(matches.values())

def get_player_match_history(player_uuid):
    sql = """
        SELECT 
            s.*,
            r.MatchID,
            m.CycleID AS CycleID
        FROM stats s
        JOIN rounds r ON s.RoundID = r.RoundID
        JOIN matches m ON r.MatchID = m.MatchID
        WHERE s.PlayerUUID = ?
        ORDER BY m.MatchID, r.RoundID;
    """
    rows = query(sql, (player_uuid,))
    return aggregate_rounds_into_matches(rows)