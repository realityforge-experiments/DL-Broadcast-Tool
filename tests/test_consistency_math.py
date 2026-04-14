import math
from tags.consistency import compute_consistency_score, build_consistency_tag

def test_consistency_score_basic():
    # Simple synthetic match performance scores
    perfs = [0.60, 0.65, 0.70, 0.75]

    floor = min(perfs)
    avg = sum(perfs) / len(perfs)
    variance = sum((x - avg) ** 2 for x in perfs) / len(perfs)
    adjusted_variance = variance * (1 + 1 / len(perfs))
    stability = 1 / (1 + adjusted_variance)

    score = compute_consistency_score(
        floor=floor,
        stability=stability,
        average=avg
    )

    assert 0.0 <= score <= 1.0
    assert score > 0.60  # should be above floor
    assert score < 0.80  # should be below average


def test_build_consistency_tag_structure():
    tag = build_consistency_tag(
        floor_current=0.60,
        floor_career=0.60,
        floor_league=0.50,
        stability_current=0.80,
        stability_career=0.80,
        stability_league=0.70,
        average_current=0.70,
        average_career=0.70,
        average_league=0.60,
        matches_played_current=10,
        percentile=None
    )

    assert hasattr(tag, "normalized_score")
    assert hasattr(tag, "percentile")
    assert hasattr(tag, "tier")
    assert hasattr(tag, "summary_short")
    assert hasattr(tag, "components")
    assert hasattr(tag, "extras")