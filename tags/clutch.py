from tags.tag_framework import build_tag_output
import math

# ---------------------------------------------------------
# Raw Clutch Score (Expanded, Meaningful Range)
# ---------------------------------------------------------

def compute_clutch_raw(player):
    career = player.get("career", {})
    # 1. Pressure Efficiency: Log-scaled but with a much higher ceiling (4000 instead of 3000)
    # This pushes average players further down the scale.
    pressure_eff = career.get("damage", 0) / (career.get("deaths", 0) + 1)
    pressure_norm = math.log1p(pressure_eff) / math.log1p(4500) 

    # 2. Consistency: Use their raw stability score
    consistency_norm = player.get("consistency", {}).get("raw", 0.5)

    # 3. Conversion: Tighten elite accuracy requirements
    shots = career.get("shots", 0)
    hit = career.get("shots_hit", 0)
    hs = career.get("headshots", 0)
    accuracy = hit / max(1, shots)
    headshot_rate = hs / max(1, hit)

    # Elite is now 30% acc / 25% HS - harder to hit 1.0
    acc_norm = min(1.0, accuracy / 0.30)
    hs_norm = min(1.0, headshot_rate / 0.25)
    conversion = (acc_norm * 0.4) + (hs_norm * 0.6)

    # 4. Weighting: Shift weight toward Pressure and Conversion
    raw = (
        pressure_norm * 0.40 +
        conversion * 0.40 +
        consistency_norm * 0.20
    )
    # Apply an exponential "curve" to create more separation at the top
    return max(0.05, min(1.0, raw ** 1.5))


# ---------------------------------------------------------
# Full Clutch Tag
# ---------------------------------------------------------

def compute_clutch(player, league_averages, clutch_distribution):

    raw = compute_clutch_raw(player)

    def summary_fn(tier, pct):
        if tier == "S":
            return "Elite closer in high-pressure moments."
        if tier == "A":
            return "Very strong under pressure."
        if tier == "B":
            return "Solid clutch performance."
        if tier == "C":
            return "Inconsistent in high-pressure moments."
        return "Struggles to close out high-pressure situations."

    return build_tag_output(raw, clutch_distribution, summary_fn)