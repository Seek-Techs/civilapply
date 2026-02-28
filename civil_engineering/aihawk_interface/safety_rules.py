MIN_LIVE_CONFIDENCE = 75

def is_safe_to_apply(job):
    return job["confidence"] >= MIN_LIVE_CONFIDENCE
