import math

def safe_pct(value):
    """
    Ensures pct is always a float between 0 and 100.
    None, NaN, or invalid → 0.0
    """
    try:
        if value is None:
            return 0.0
        v = float(value)
        if math.isnan(v):
            return 0.0
        return max(0.0, min(100.0, v))
    except:
        return 0.0


def safe_tier(value):
    """
    Ensures tier is always a valid letter.
    None or empty → 'D'
    """
    if value in (None, "", "None"):
        return "D"
    return str(value)


def safe_summary(value):
    """
    Ensures summary is always a string.
    """
    if value is None:
        return ""
    return str(value)


def safe_raw(value):
    """
    Ensures raw is always a float.
    """
    try:
        if value is None:
            return 0.0
        v = float(value)
        if math.isnan(v):
            return 0.0
        return v
    except:
        return 0.0


def safe_tag(tag_dict):
    """
    Normalizes an entire tag dict.
    Guarantees all fields exist and are safe.
    """
    if not isinstance(tag_dict, dict):
        return {
            "raw": 0.0,
            "pct": 0.0,
            "tier": "D",
            "summary": ""
        }

    return {
        "raw": safe_raw(tag_dict.get("raw")),
        "pct": safe_pct(tag_dict.get("pct")),
        "tier": safe_tier(tag_dict.get("tier")),
        "summary": safe_summary(tag_dict.get("summary"))
    }


def safe_avg(values):
    """
    Averages a list of pct values safely.
    None, NaN, invalid → treated as 0.0
    """
    cleaned = [safe_pct(v) for v in values]
    if not cleaned:
        return 0.0
    return sum(cleaned) / len(cleaned)