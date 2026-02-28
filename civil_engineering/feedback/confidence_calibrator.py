# civil_engineering/feedback/confidence_calibrator.py

from civil_engineering.feedback.confidence_adjuster import get_confidence_adjustment


def calibrate_confidence(base_confidence: float, normalized_signals: dict) -> float:
    """
    Apply bounded historical adjustment to base confidence
    using prior outcomes for similar signal buckets.
    """

    adjustment = get_confidence_adjustment(normalized_signals)
    final_confidence = base_confidence + adjustment

    # Hard clamp
    return max(0, min(100, round(final_confidence, 1)))
