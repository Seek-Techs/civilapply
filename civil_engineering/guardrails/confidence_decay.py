# civil_engineering/guardrails/confidence_decay.py

def apply_confidence_decay(job, previous_applications):
    """
    Reduces confidence if similar roles were already applied for.
    """

    base_confidence = job["confidence"]
    title = job.get("job_title")

    repeats = sum(
        1 for app in previous_applications
        if app.get("job_title") == title
    )

    if repeats == 0:
        return base_confidence
    elif repeats == 1:
        return base_confidence - 5
    elif repeats == 2:
        return base_confidence - 12
    else:
        return 0  # hard block

