# # civil_engineering/guardrails/guardrail_engine.py

# from datetime import date
# from civil_engineering.guardrails.limits import APPLICATION_LIMITS
# from civil_engineering.guardrails.tracker import load_tracker
# from civil_engineering.guardrails.confidence_decay import apply_confidence_decay


# def guardrail_verdict(job_summary):
#     """
#     Returns one of:
#     - allow_auto_apply
#     - require_human_review
#     - blocked_by_guardrails
#     """

#     tracker = load_tracker()

#     # Reset tracker daily
#     if tracker.get("date") != str(date.today()):
#         tracker["date"] = str(date.today())
#         tracker["applications"] = []

#     applications = tracker["applications"]

#     # 1. Daily cap
#     if len(applications) >= APPLICATION_LIMITS["daily_limit"]:
#         return "blocked_by_guardrails", "Daily application limit reached"

#     # 2. Confidence decay
#     adjusted_confidence = apply_confidence_decay(
#         job_summary,
#         applications
#     )

#     if adjusted_confidence <= 0:
#         return "blocked_by_guardrails", "Repeated role confidence decay"

#     # 3. Final decision
#     if adjusted_confidence >= 70:
#         return "allow_auto_apply", None

#     if adjusted_confidence >= 50:
#         return "require_human_review", None

#     return "blocked_by_guardrails", "Low post-guardrail confidence"

# civil_engineering/guardrails/guardrail_engine.py
#
# ── WHAT THIS FILE DOES ──────────────────────────────────────────────────────
# Final safety gate before any application is submitted.
# Checks daily limits and applies confidence decay for repeated titles.
#
# ── WHAT CHANGED ─────────────────────────────────────────────────────────────
# Updated call to apply_confidence_decay() to match the fixed signature.
# Now passes confidence VALUE and job_title explicitly, not the whole job dict.
#
# ── SENIOR DEV CONCEPT: Keeping the call site clean ─────────────────────────
# When you fix a function's signature, you must update every place that
# calls it. This is called "updating the call sites."
# A good IDE or grep will find them all:
#   grep -r "apply_confidence_decay" .

from datetime import date
from civil_engineering.guardrails.limits import APPLICATION_LIMITS
from civil_engineering.guardrails.tracker import load_tracker
from civil_engineering.guardrails.confidence_decay import apply_confidence_decay


def guardrail_verdict(job_summary: dict) -> tuple[str, str | None]:
    """
    Check whether to allow, review, or block an application.

    Args:
        job_summary: The job_summary dict (must have "confidence" and "job_title" keys)

    Returns:
        Tuple of (verdict, reason_or_None)
        verdict is one of:
          "allow_auto_apply"      — proceed automatically
          "require_human_review"  — score is borderline, needs human eyes
          "blocked_by_guardrails" — do not apply

    WHY RETURN A TUPLE?
    The verdict alone isn't enough — callers need to know WHY something was
    blocked so they can log it or display it to the user.
    A tuple(verdict, reason) gives both in one return value.
    """
    tracker      = load_tracker()
    today_str    = str(date.today())

    # Reset daily tracker if the date has changed
    # WHY CHECK THE DATE? The tracker is persisted to disk (tracker.json).
    # If yesterday's data wasn't cleared, today's limit would be pre-exhausted.
    if tracker.get("date") != today_str:
        tracker["date"]         = today_str
        tracker["applications"] = []

    applications = tracker.get("applications", [])

    # ── Gate 1: Daily cap ─────────────────────────────────────────────────────
    daily_limit = APPLICATION_LIMITS["daily_limit"]
    if len(applications) >= daily_limit:
        return "blocked_by_guardrails", f"Daily limit of {daily_limit} applications reached"

    # ── Gate 2: Confidence decay for repeated titles ──────────────────────────
    # FIXED: Now passes explicit values instead of the whole job dict
    base_confidence = job_summary.get("confidence", 0)
    job_title       = job_summary.get("job_title")

    adjusted_confidence = apply_confidence_decay(
        base_confidence=base_confidence,
        job_title=job_title,
        previous_applications=applications,
    )

    if adjusted_confidence <= 0:
        return "blocked_by_guardrails", f"Confidence decayed to 0 after repeated applications to '{job_title}'"

    # ── Gate 3: Final decision based on adjusted confidence ───────────────────
    if adjusted_confidence >= 70:
        return "allow_auto_apply", None

    if adjusted_confidence >= 50:
        return "require_human_review", None

    return "blocked_by_guardrails", f"Post-decay confidence {adjusted_confidence:.0f} is below threshold"