# civil_engineering/feedback/confidence_adjuster.py

from collections import defaultdict
from datetime import datetime, timedelta

from civil_engineering.feedback.outcome_store import load_outcomes
from civil_engineering.feedback.decision_log_store import load_decisions
from civil_engineering.feedback.human_override_store import load_overrides
from civil_engineering.feedback.signal_hashing import hash_signal_bucket



# --- Hard limits (safety first) ---
MAX_POSITIVE_ADJUSTMENT = 5.0
MAX_NEGATIVE_ADJUSTMENT = -5.0

DECAY_DAYS = 30  # outcomes older than this fade out

# --- Outcome weights (fixed, explainable) ---
OUTCOME_WEIGHTS = {
    "applied": -0.5,
    "viewed": 0.5,
    "interview": 2.0,
    "rejected": -1.0,
    "offer": 5.0
}

HUMAN_OVERRIDE_WEIGHTS = {
    "force_apply": 2.0,
    "force_skip": -2.0
}


# def _hash_signal_bucket(signals: dict) -> str:
#     """
#     Convert normalized signals into a stable bucket key.
#     """
#     parts = []
#     for key in sorted(signals.keys()):
#         values = ",".join(sorted(signals[key]))
#         parts.append(f"{key}:{values}")
#     return "|".join(parts)


def _is_recent(timestamp: str) -> bool:
    dt = datetime.fromisoformat(timestamp)
    return datetime.utcnow() - dt <= timedelta(days=DECAY_DAYS)


def get_confidence_adjustment(normalized_signals: dict) -> float:
    """
    Compute bounded confidence adjustment based on historical outcomes
    for similar signal buckets.
    """
    decisions = load_decisions()
    outcomes = load_outcomes()

    bucket_key = hash_signal_bucket(normalized_signals)

    delta = 0.0

    for decision in decisions:
        if decision["signal_bucket"] != bucket_key:
            continue

        job_id = decision["job_id"]

        outcome = outcomes.get(job_id)
        if not outcome:
            continue

        if not _is_recent(outcome["timestamp"]):
            continue

        weight = OUTCOME_WEIGHTS.get(outcome["outcome"], 0)
        delta += weight

        from civil_engineering.feedback.override_store import load_overrides

        overrides = load_overrides()

        for override in overrides:
            if override["job_id"] == job_id:
                if override["override_type"] == "force_apply":
                    delta += 1.0
                elif override["override_type"] == "force_skip":
                    delta -= 1.0

    # --- Clamp adjustment ---
    delta = max(MAX_NEGATIVE_ADJUSTMENT, min(MAX_POSITIVE_ADJUSTMENT, delta))
    return round(delta, 2)
