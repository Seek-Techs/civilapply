def record_human_feedback(job_id, feedback):
    """
    feedback: "good_decision" | "bad_decision" | "neutral"
    """
    return {
        "job_id": job_id,
        "human_feedback": feedback
    }
