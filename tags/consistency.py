import math

def compute_consistency(matches):
    """
    matches = list of dicts, each containing:
        - kills
        - deaths
        - accuracy
        - damage
        - push_time (payload)
        - captures
        - counters
        - mode
    """

    # --- Not enough matches to compute variance ---
    if len(matches) < 2:
        return 0.0, {
            "per_match_perf": [],
            "floor": 0.0,
            "variance": 0.0,
            "variance_adj": 0.0,
            "variance_score": 0.0,
            "avg_perf": 0.0,
            "consistency_norm": 0.0
        }

    per_match_perf_list = []

    for m in matches:

        # --- Slayer percentile (per match) ---
        kd = m["kills"] / max(1, m["deaths"])
        slayer_pct = percentile_of_kd(kd)

        # --- Objective percentile (per match) ---
        if m["mode"] == "payload":
            obj_raw = m["push_time"]
        elif m["mode"] == "domination":
            obj_raw = m["captures"] + m["counters"]
        else:
            obj_raw = 0

        objective_pct = percentile_of_objective(obj_raw)

        # --- Accuracy percentile (per match) ---
        accuracy_pct = percentile_of_accuracy(m["accuracy"])

        # --- Composite per-match performance ---
        perf = (
            slayer_pct * 0.40 +
            objective_pct * 0.40 +
            accuracy_pct * 0.20
        )

        per_match_perf_list.append(perf)

    # --- Floor ---
    floor_score = percentile(min(per_match_perf_list))

    # --- Variance (normalized by match count) ---
    raw_variance = variance(per_match_perf_list)
    adj_variance = raw_variance * (1 + (1 / len(matches)))
    variance_score = 1 / (1 + adj_variance)

    # --- Average performance ---
    avg_perf = sum(per_match_perf_list) / len(per_match_perf_list)

    # --- Final Consistency ---
    consistency_raw = (
        floor_score * 0.40 +
        variance_score * 0.40 +
        avg_perf * 0.20
    )

    # --- Normalized consistency (already 0–1) ---
    consistency_norm = round(consistency_raw, 4)

    # --- Component block returned to DB builder ---
    components = {
        "per_match_perf": per_match_perf_list,
        "floor": floor_score,
        "variance": raw_variance,
        "variance_adj": adj_variance,
        "variance_score": variance_score,
        "avg_perf": avg_perf,
        "consistency_norm": consistency_norm
    }

    return consistency_norm, components