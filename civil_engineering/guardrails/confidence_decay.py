# # civil_engineering/guardrails/confidence_decay.py

# def apply_confidence_decay(job, previous_applications):
#     """
#     Reduces confidence if similar roles were already applied for.
#     """

#     base_confidence = job["confidence"]
#     title = job.get("job_title")

#     repeats = sum(
#         1 for app in previous_applications
#         if app.get("job_title") == title
#     )

#     if repeats == 0:
#         return base_confidence
#     elif repeats == 1:
#         return base_confidence - 5
#     elif repeats == 2:
#         return base_confidence - 12
#     else:
#         return 0  # hard block


# civil_engineering/guardrails/confidence_decay.py
#
# ── WHAT THIS FILE DOES ──────────────────────────────────────────────────────
# Reduces confidence when the candidate has already applied to similar roles.
# The logic: if you've applied to 3 "Site Engineer" jobs today and they're
# not responding, keep sending more is likely a bad strategy.
#
# ── BUG FIXED: KeyError on job["confidence"] ─────────────────────────────────
# ORIGINAL CODE:
#
#   def apply_confidence_decay(job, previous_applications):
#       base_confidence = job["confidence"]   ← CRASH
#
# WHERE IS THIS CALLED FROM?
# guardrail_engine.py calls it like this:
#
#   adjusted_confidence = apply_confidence_decay(job_summary, applications)
#
# And job_summary is passed in as the raw job dict loaded from disk:
#   with open(job_file) as f:
#       job = json.load(f)
#
# A raw job JSON looks like:
#   {"title": "Site Engineer", "years_required": 3, "project_types": [...]}
#
# There is NO "confidence" key in a raw job file.
# Confidence is computed LATER by calculate_confidence().
# So job["confidence"] raises KeyError every single time.
#
# FIX:
# The function should receive the CONFIDENCE VALUE as a direct argument,
# not try to extract it from the job dict.
# This separates concerns: the caller is responsible for computing confidence,
# this function is responsible for applying decay to it.
#
# ── SENIOR DEV CONCEPT: "Don't reach into objects for what you need" ─────────
# If a function needs a specific VALUE, pass that value directly.
# Don't make the function dig into an object to find it.
#
# BAD:  apply_confidence_decay(job, ...)  ← function assumes job has "confidence"
# GOOD: apply_confidence_decay(confidence, job_title, ...)  ← explicit


def apply_confidence_decay(
    base_confidence: float,
    job_title: str | None,
    previous_applications: list[dict],
) -> float:
    """
    Apply decay to a confidence score based on how many similar roles
    have already been applied to in the current session.

    The more repeat applications to the same title, the lower the adjusted
    confidence — signalling diminishing returns on the same strategy.

    Args:
        base_confidence:        The raw confidence score (0–100)
        job_title:              Title of the current job (used for repeat detection)
        previous_applications:  List of application dicts from the tracker

    Returns:
        Adjusted confidence score (float, clamped to 0 minimum)

    Decay schedule:
        0 repeats → no decay        (fresh title, full confidence)
        1 repeat  → -5 points       (tried once, minor reduction)
        2 repeats → -12 points      (tried twice, notable reduction)
        3+ repeats → 0 (hard block) (saturated, stop applying to this title)
    """
    if not job_title:
        # No title to compare against — can't detect repeats, return as-is
        return base_confidence

    # Count how many previous applications had the same job title
    repeats = sum(
        1 for app in previous_applications
        if app.get("job_title") == job_title
    )

    if repeats == 0:
        return base_confidence
    elif repeats == 1:
        return max(0.0, base_confidence - 5)
    elif repeats == 2:
        return max(0.0, base_confidence - 12)
    else:
        # 3+ repeats: hard block — return 0 to trigger the guardrail
        return 0.0