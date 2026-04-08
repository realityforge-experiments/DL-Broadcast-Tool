import math

def compute_dom_objective(player_entry):
    """
    Domination Objective Specialist (ObjDOM)

    Uses only website stats:
      - DOM_captures
      - DOM_counters

    Log-scaled normalization:
        CapRate      = log(1 + captures) / log(1 + 20)
        CounterRate  = log(1 + counters) / log(1 + 20)

    Formula (0–1 scale):
        ObjDOM = 0.40 * CapRate + 0.60 * CounterRate

    Counters are weighted more heavily because they prevent enemy scoring.
    """

    caps = player_entry.get("DOM_captures", 0) or 0
    counters = player_entry.get("DOM_counters", 0) or 0

    # Log-scaled normalization (smooths extremes, expands mid-range)
    cap_rate = math.log1p(caps) / math.log1p(20)
    counter_rate = math.log1p(counters) / math.log1p(20)

    score = (0.40 * cap_rate) + (0.60 * counter_rate)
    return round(score, 3)