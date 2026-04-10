from tags.tag_framework import build_tag_output
import math

# ---------------------------------------------------------
# Raw Clutch Score (Expanded, Meaningful Range)
# ---------------------------------------------------------

def compute_clutch_raw(player):
    """
    Computes a meaningful 0–1 clutch score with real separation.
    Components:
        - pressure efficiency (log-scaled)
        - high-pressure accuracy (expanded)
        - consistency (smoothed)
        - clutch moment density (rare-event amplifier)
    """

    career = player.get("career", {})
    dmg = career.get("damage", 0)
    deaths = career.get("deaths", 0)
    shots = career.get("shots", 0)
    shots_hit = career.get("shots_hit", 0)
    headshots = career.get("headshots", 0)

    # -----------------------------------------
    # 1. Pressure Efficiency (log-scaled)
    # -----------------------------------------
    pressure_eff = dmg / (deaths + 1)
    pressure_norm = math.log1p(pressure_eff) / math.log1p(3000)

    # -----------------------------------------
    # 2. Consistency (smoothed)
    # -----------------------------------------
    consistency = player.get("consistency", {})
    consistency_norm = consistency.get("raw", 0.0)
    consistency_norm = max(0.1, consistency_norm)  # avoid collapse

    # -----------------------------------------
    # 3. Accuracy + Headshot Rate (expanded)
    # -----------------------------------------
    accuracy = shots_hit / max(1, shots)
    headshot_rate = headshots / max(1, shots_hit)

    acc_norm = min(1.0, accuracy / 0.25)          # 25% = elite
    hs_norm = min(1.0, headshot_rate / 0.20)      # 20% = elite

    conversion = (acc_norm * 0.4) + (hs_norm * 0.6)

    # -----------------------------------------
    # 4. Clutch Moment Density (rare-event amplifier)
    # -----------------------------------------
    matches = player.get("matches", [])
    clutch_events = 0

    for m in matches:
        # Count high-pressure events (kills in final minute, etc.)
        # We don't have real clutch stats, so approximate:
        if m.get("Kills", 0) >= 10:
            clutch_events += 1

    density = clutch_events / max(1, len(matches))
    density_norm = min(1.0, density * 3.0)  # amplify rare events

    # -----------------------------------------
    # Final weighted score (expanded)
    # -----------------------------------------
    raw = (
        pressure_norm * 0.35 +
        consistency_norm * 0.25 +
        conversion * 0.25 +
        density_norm * 0.15
    )

    return max(0.05, min(1.0, raw))


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