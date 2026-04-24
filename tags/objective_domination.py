import math
from tags.tag_framework import build_tag_output

# ---------------------------------------------------------
# Domination Summary
# ---------------------------------------------------------

def dom_summary(tier, pct):
    if tier == "S":
        return f"Elite Domination specialist — top {100 - pct:.0f}% in captures and counters."
    if tier == "A":
        return "Strong Domination presence with high counter impact."
    if tier == "B":
        return "Above-average Domination contribution."
    if tier == "C":
        return "Below-average Domination presence."
    return "Minimal Domination impact."


# ---------------------------------------------------------
# Raw Domination Score (Career)
# ---------------------------------------------------------

def compute_dom_raw(pdata):
    # Try career totals first
    caps = pdata.get("career", {}).get("DOM_Captures") or pdata.get("DOM_Captures") or 0
    counters = pdata.get("career", {}).get("DOM_Counters") or pdata.get("DOM_Counters") or 0
    maps = max(1, pdata.get("career", {}).get("maps") or 1)

    # If no career totals, try matches
    if caps == 0 and counters == 0:
        matches = pdata.get("matches", [])
        for m in matches:
            caps += m.get("DOM_Captures", 0) or m.get("DOM_captures", 0)
            counters += m.get("DOM_Counters", 0) or m.get("DOM_counters", 0)
    
    avg_caps = caps / maps
    avg_counters = counters / maps

    # Use a lower log base to make small numbers more visible to the score
    cap_rate = math.log1p(avg_caps) / math.log1p(10.0) 
    counter_rate = math.log1p(avg_counters) / math.log1p(10.0)

    raw = (0.40 * cap_rate) + (0.60 * counter_rate)
    return max(0.05, min(raw, 1.0))


# ---------------------------------------------------------
# Public API — Career Tag
# ---------------------------------------------------------

def compute_dom_objective_for_career_player(pdata, league_averages, dom_distribution):
    """
    Career Domination Objective Specialist tag.
    Uses DOM_Captures and DOM_Counters from career totals.
    Log-scaled normalization + weighted scoring.
    """

    caps = pdata.get("DOM_Captures", 0) or 0
    counters = pdata.get("DOM_Counters", 0) or 0

    # Log-scaled normalization (smooths extremes)
    cap_rate = math.log1p(caps) / math.log1p(20)
    counter_rate = math.log1p(counters) / math.log1p(20)

    # Weighted score (counters matter more)
    raw = (0.40 * cap_rate) + (0.60 * counter_rate)

    # Convert to percentile + tier
    return build_tag_output(raw, dom_distribution, dom_summary)


# ---------------------------------------------------------
# Match-Based Extraction (unchanged)
# ---------------------------------------------------------

def compute_dom_objective_for_match_player(p):
    caps = p.get("DOM_Captures", 0) or 0
    counters = p.get("DOM_Counters", 0) or 0
    return {"captures": caps, "counters": counters}


# ---------------------------------------------------------
# Match-Based Team Scores (unchanged)
# ---------------------------------------------------------

def compute_dom_objective_team_scores(team_entries):
    team_caps = sum(mp.get("DOM_Captures", 0) or 0 for _, _, mp in team_entries)
    team_counters = sum(mp.get("DOM_Counters", 0) or 0 for _, _, mp in team_entries)

    if team_caps <= 0:
        team_caps = 1
    if team_counters <= 0:
        team_counters = 1

    scores = {}

    for pid, entry, mp in team_entries:
        caps = mp.get("DOM_Captures", 0) or 0
        counters = mp.get("DOM_Counters", 0) or 0

        cap_presence = caps / team_caps
        counter_presence = counters / team_counters

        cap_rate = math.log1p(caps) / math.log1p(10.0)
        counter_rate = math.log1p(counters) / math.log1p(10.0)

        cap_component = 0.5 * cap_presence + 0.5 * cap_rate
        counter_component = 0.5 * counter_presence + 0.5 * counter_rate

        score = (0.40 * cap_component) + (0.60 * counter_component)
        scores[pid] = round(score, 4)

    return scores