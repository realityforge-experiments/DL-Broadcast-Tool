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
    """
    Computes a normalized 0–1 Domination Objective Specialist score.
    Uses ONLY Domination stats:
        - captures
        - counters
    """

    matches = pdata.get("matches", [])
    if not matches:
        return 0.05  # minimum floor

    dom_matches = 0
    total_caps = 0
    total_counters = 0

    for m in matches:
        caps = m.get("DOM_Captures", 0) or 0
        counters = m.get("DOM_Counters", 0) or 0

        # Skip matches with no DOM stats
        if caps == 0 and counters == 0:
            continue

        dom_matches += 1
        total_caps += caps
        total_counters += counters

    if dom_matches == 0:
        return 0.05  # minimum floor

    avg_caps = total_caps / dom_matches
    avg_counters = total_counters / dom_matches

    # Log-scaled normalization (smooth extremes, expand mid-range)
    cap_rate = math.log1p(avg_caps) / math.log1p(15.0)
    counter_rate = math.log1p(avg_counters) / math.log1p(15.0)

    # Counters weighted more heavily (deny enemy scoring)
    raw = (0.40 * cap_rate) + (0.60 * counter_rate)

    # Soft clamp
    raw = max(0.05, min(raw, 1.0))
    return raw


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