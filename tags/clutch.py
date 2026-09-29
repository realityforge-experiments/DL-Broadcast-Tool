from tags.tag_framework import build_tag_output
import math

# ---------------------------------------------------------
# Raw Clutch Score (Expanded, Meaningful Range)
# ---------------------------------------------------------

def compute_clutch_raw(player, league_averages=None):
    career = player.get("career", {})
    # 1. Pressure Efficiency: log-scaled ceiling based on real league
    # activity with headroom (4x league average), instead of a flat,
    # guessed 4500 — which turned out to be ~44x the actual league
    # average pressure_eff (~103), meaning even elite players could
    # barely approach 1.0 on this 40%-weighted component. That over-
    # compressed the whole tag toward the bottom of the range instead
    # of reflecting ability across the full skill spectrum.
    pressure_eff = career.get("damage", 0) / (career.get("deaths", 0) + 1)
    league_avg_pressure = (league_averages or {}).get("pressure_eff", 103) or 103
    pressure_ceiling = max(200, league_avg_pressure * 4)
    pressure_norm = math.log1p(pressure_eff) / math.log1p(pressure_ceiling)

    # 2. Consistency: Use their raw stability score. NOTE: read the
    # FLAT "consistency_raw" key, not the nested "consistency"/"raw"
    # dict — the nested dict isn't populated until later in
    # build_career_database's pipeline, so when this function runs
    # during distribution-building (before that point), the nested
    # lookup always silently fell back to the 0.5 default for every
    # single player. That corrupted the distribution used for
    # percentile ranking: real per-player Clutch scores (computed
    # later, once the nested dict existed) were being ranked against a
    # population that never actually varied on this 20%-weighted
    # component, compressing/skewing every percentile. The flat key is
    # populated early and consistently, so reading it here keeps the
    # distribution and the final score using the same real values.
    consistency_norm = player.get("consistency_raw", 0.5)

    # 3. Conversion: accuracy/headshot ceilings (0.30/0.25) are ~2.3x
    # the real league averages (~0.13/~0.11) — already well-calibrated
    # real headroom, left unchanged.
    shots = career.get("shots", 0)
    hit = career.get("shots_hit", 0)
    hs = career.get("headshots", 0)
    accuracy = hit / max(1, shots)
    headshot_rate = hs / max(1, hit)

    acc_norm = min(1.0, accuracy / 0.30)
    hs_norm = min(1.0, headshot_rate / 0.25)
    conversion = (acc_norm * 0.4) + (hs_norm * 0.6)

    # 4. Weighting
    raw = (
        pressure_norm * 0.40 +
        conversion * 0.40 +
        consistency_norm * 0.20
    )
    # The exponential curve (raw ** 1.5) that used to sit here has been
    # removed — for any raw < 1.0, raising it to a power > 1 pushes the
    # value DOWN further, which was compounding the pressure_eff
    # ceiling issue above by squashing average/decent players even
    # closer to the bottom instead of spreading the full spectrum out
    # evenly. A plain clamp reflects ability across the range more
    # fairly.
    return max(0.05, min(1.0, raw))


# ---------------------------------------------------------
# Full Clutch Tag
# ---------------------------------------------------------

def compute_clutch(player, league_averages, clutch_distribution):

    raw = compute_clutch_raw(player, league_averages)

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