# civil_engineering/guardrails/guardrail_engine.py

from datetime import date
from civil_engineering.guardrails.limits import APPLICATION_LIMITS
from civil_engineering.guardrails.tracker import load_tracker
from civil_engineering.guardrails.confidence_decay import apply_confidence_decay


def guardrail_verdict(job_summary):
    """
    Returns one of:
    - allow_auto_apply
    - require_human_review
    - blocked_by_guardrails
    """

    tracker = load_tracker()

    # Reset tracker daily
    if tracker.get("date") != str(date.today()):
        tracker["date"] = str(date.today())
        tracker["applications"] = []

    applications = tracker["applications"]

    # 1. Daily cap
    if len(applications) >= APPLICATION_LIMITS["daily_limit"]:
        return "blocked_by_guardrails", "Daily application limit reached"

    # 2. Confidence decay
    adjusted_confidence = apply_confidence_decay(
        job_summary,
        applications
    )

    if adjusted_confidence <= 0:
        return "blocked_by_guardrails", "Repeated role confidence decay"

    # 3. Final decision
    if adjusted_confidence >= 70:
        return "allow_auto_apply", None

    if adjusted_confidence >= 50:
        return "require_human_review", None

    return "blocked_by_guardrails", "Low post-guardrail confidence"
