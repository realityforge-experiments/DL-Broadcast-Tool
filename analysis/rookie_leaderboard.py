def compute_rookie_leaderboard(career_db, tag="slayer", limit=10):
    rookies = []

    for cid, pdata in career_db["players"].items():
        maps = pdata["career"].get("maps", 0)
        if maps >= 10:
            continue  # not a rookie

        tag_data = pdata.get(tag, {})
        rookies.append({
            "canonical_id": cid,
            "name": pdata["name"],
            "team": pdata.get("team", ""),
            "maps": maps,
            "kd": pdata["career"]["KD"],
            "kills": pdata["career"]["kills"],
            "score": pdata["career"]["damage"],  # or actual score if available
            "tag_raw": tag_data.get("raw", 0.0),
            "tag_pct": tag_data.get("pct", 0.0),
            "tag_tier": tag_data.get("tier", "D"),
        })

    rookies.sort(key=lambda r: r["tag_pct"], reverse=True)
    return rookies[:limit]