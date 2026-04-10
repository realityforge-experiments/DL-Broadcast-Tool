from tags.tag_framework import build_tag_output

# ---------------------------------------------------------
# Sharpshooter Summary
# ---------------------------------------------------------

def sharpshooter_summary(tier, pct):
    if tier == "S":
        return f"Elite marksman — top {100 - pct:.0f}% in accuracy and headshots."
    if tier == "A":
        return "High-accuracy shooter with strong headshot presence."
    if tier == "B":
        return "Above-average accuracy and headshot conversion."
    if tier == "C":
        return "Below-average accuracy and headshot rate."
    return "Struggles to land shots consistently."


# ---------------------------------------------------------
# Raw Sharpshooter Score (Robust)
# ---------------------------------------------------------

def compute_sharpshooter_raw(career, league_averages):
    shots = career.get("shots", 0)
    hit = career.get("shots_hit", 0)
    hs = career.get("headshots", 0)

    # Avoid zero-division and missing data
    if shots < 10 or hit < 5:
        return 0.05  # minimum floor to avoid clustering at 0

    accuracy = hit / shots
    hs_rate = hs / hit if hit > 0 else 0

    # League smoothing
    league_acc = max(league_averages.get("accuracy", 0.05), 0.05)
    league_hs = max(league_averages.get("headshot_rate", 0.03), 0.03)

    acc_norm = accuracy / league_acc
    hs_norm = hs_rate / league_hs

    # Weighted raw score
    raw = (acc_norm * 0.6) + (hs_norm * 0.4)

    # Soft clamp (not hard 0–1)
    raw = max(0.05, min(raw, 1.5))

    # Normalize into 0–1 range
    return raw / 1.5


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def compute_sharpshooter_for_career_player(career, league_averages, sharpshooter_distribution):
    raw = compute_sharpshooter_raw(career, league_averages)
    return build_tag_output(raw, sharpshooter_distribution, sharpshooter_summary)