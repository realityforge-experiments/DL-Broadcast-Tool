from utils.safe_tag import safe_raw

# ---------------------------------------------------------
# RAW SCORE CALCULATION
# ---------------------------------------------------------


def compute_support_specialist(player, league_averages):
    c = player.get("career", {})

    dmg = safe_raw(c.get("damage"))
    deaths = safe_raw(c.get("deaths"))
    push_time = safe_raw(c.get("push_time"))
    dom_caps = safe_raw(c.get("captures"))
    dom_counters = safe_raw(c.get("counters"))

    # League anchors
    league_push = max(1.0, league_averages.get("push_time", 1.0))
    league_dom_actions = max(1.0, league_averages.get("dom_actions", 1.0))
    league_damage = max(1.0, league_averages.get("damage", 1.0))
    league_deaths = max(1.0, league_averages.get("deaths", 1.0))
    league_pressure = max(1e-6, league_averages.get("pressure_eff", 1.0))

    # Objective presence (relative to league, capped)
    presence_payload = (push_time / league_push)
    presence_dom = ((dom_caps + dom_counters) / league_dom_actions)
    objective_presence = max(presence_payload, presence_dom)
    objective_presence = max(0.0, min(objective_presence, 2.0))

    # Survivability: pressure vs league pressure_eff
    player_pressure = dmg / max(1.0, deaths)
    survivability = player_pressure / league_pressure
    survivability = max(0.0, min(survivability, 2.0))

    # Damage component: relative to league damage
    damage_component = dmg / league_damage
    damage_component = max(0.0, min(damage_component, 2.0))

    # Low-death bonus: 1 is good, 0 is bad
    low_death_bonus = 1.0 - (deaths / league_deaths)
    low_death_bonus = max(0.0, min(low_death_bonus, 1.0))

    # Weighted sum, then scale back into 0–1
    raw = (
        0.35 * objective_presence +
        0.35 * survivability +
        0.20 * damage_component +
        0.10 * low_death_bonus
    ) / 2.0  # max of the capped components is 2 → divide by 2 to keep ≤ 1

    return raw

# ---------------------------------------------------------
# TAG BUILDER (RAW → PERCENTILE → TIER → SUMMARY)
# ---------------------------------------------------------

def build_support_specialist_tag(player, league_averages, distribution):
    """
    Converts raw Support Specialist score into full tag output.
    """

    from tags.tag_framework import build_tag_output

    raw = compute_support_specialist(player, league_averages)

    def summary_fn(tier, pct):
        if pct >= 85:
            return "Elite support presence — stabilizes fights and enables strong objective pushes."
        if pct >= 70:
            return "Reliable support player with strong survivability and objective presence."
        if pct >= 50:
            return "Provides steady support value through survivability and objective actions."
        if pct >= 30:
            return "Occasional support impact but inconsistent objective presence."
        return "Limited support impact — low survivability and minimal objective presence."

    return build_tag_output(raw, distribution, summary_fn)