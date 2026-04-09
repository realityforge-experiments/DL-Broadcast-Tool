import math

# ---------------------------------------------------------
# 1. CAREER DOMINATION OBJECTIVE SPECIALIST (ObjDOM)
# ---------------------------------------------------------

def compute_dom_objective_for_career_player(pdata, league_averages=None):
    """
    Compute a career Domination Objective score using ONLY Domination stats.

    A "Domination map" is any match where DOM_Captures > 0 or DOM_Counters > 0.
    Payload and Control Point stats are ignored.
    """

    matches = pdata.get("matches", [])
    if not matches:
        return {
            "dom_matches": 0,
            "total_captures": 0,
            "total_counters": 0,
            "avg_captures": 0.0,
            "avg_counters": 0.0,
            "dom_score_raw": 0.0,
            "dom_score_display": "0.00",
        }

    dom_matches = 0
    total_caps = 0
    total_counters = 0

    for m in matches:
        caps = m.get("DOM_Captures", 0) or 0
        counters = m.get("DOM_Counters", 0) or 0

        # Only count Domination maps
        if caps > 0 or counters > 0:
            dom_matches += 1
            total_caps += caps
            total_counters += counters

    if dom_matches == 0:
        return {
            "dom_matches": 0,
            "total_captures": 0,
            "total_counters": 0,
            "avg_captures": 0.0,
            "avg_counters": 0.0,
            "dom_score_raw": 0.0,
            "dom_score_display": "0.00",
        }

    avg_caps = total_caps / dom_matches
    avg_counters = total_counters / dom_matches

    # Log-scaled normalization (smooth extremes, expand mid-range)
    # Soft caps: ~20 caps / 20 counters across career
    cap_rate = math.log1p(avg_caps) / math.log1p(20.0)
    counter_rate = math.log1p(avg_counters) / math.log1p(20.0)

    # Counters weighted more heavily (deny enemy scoring)
    raw = (0.40 * cap_rate) + (0.60 * counter_rate)

    return {
        "dom_matches": dom_matches,
        "total_captures": total_caps,
        "total_counters": total_counters,
        "avg_captures": avg_caps,
        "avg_counters": avg_counters,
        "dom_score_raw": raw,
        "dom_score_display": f"{raw:.2f}",
    }


# ---------------------------------------------------------
# 2. MATCH-BASED DOMINATION OBJECTIVE SPECIALIST
# ---------------------------------------------------------

def compute_dom_objective_for_match_player(p):
    """
    Extract match-level Domination stats for a single player.
    Used only for match-based ObjDOM.
    """

    caps = p.get("DOM_Captures", 0) or 0
    counters = p.get("DOM_Counters", 0) or 0

    return {
        "captures": caps,
        "counters": counters,
    }


# ---------------------------------------------------------
# 3. TEAM SCORE CALCULATION (MATCH-BASED ObjDOM)
# ---------------------------------------------------------

def compute_dom_objective_team_scores(team_entries):
    """
    team_entries = list of (pid, entry, match_player)
    entry = career DB entry (ignored for match ObjDOM)
    match_player = match player dict with DOM stats
    """

    # Total team captures / counters
    team_caps = sum(mp.get("DOM_Captures", 0) or 0 for _, _, mp in team_entries)
    team_counters = sum(mp.get("DOM_Counters", 0) or 0 for _, _, mp in team_entries)

    # Avoid division by zero
    if team_caps <= 0:
        team_caps = 1
    if team_counters <= 0:
        team_counters = 1

    scores = {}

    for pid, entry, mp in team_entries:
        caps = mp.get("DOM_Captures", 0) or 0
        counters = mp.get("DOM_Counters", 0) or 0

        # 1. Presence on objective (share of team captures)
        cap_presence = caps / team_caps

        # 2. Counter presence (share of team counters)
        counter_presence = counters / team_counters

        # 3. Log scaling to smooth extremes
        cap_rate = math.log1p(caps) / math.log1p(10.0)      # per-map soft cap ~10 caps
        counter_rate = math.log1p(counters) / math.log1p(10.0)

        # Blend presence + impact
        # Captures: both presence + rate
        # Counters: weighted more heavily (deny enemy scoring)
        cap_component = 0.5 * cap_presence + 0.5 * cap_rate
        counter_component = 0.5 * counter_presence + 0.5 * counter_rate

        score = (0.40 * cap_component) + (0.60 * counter_component)

        scores[pid] = round(score, 4)

    return scores