from civil_engineering.feedback.attribution_engine import attribute_outcome
from civil_engineering.feedback.confidence_calibrator import calibrate_confidence
from civil_engineering.feedback.decision_log_store import load_decision_log


def process_outcome(job_id, job, outcome):
    decision_log = load_decision_log(job_id)

    insights = attribute_outcome(job, decision_log, outcome)

    base_conf = job.get("confidence", 50)
    new_conf = calibrate_confidence(base_conf, outcome)

    return {
        "job_id": job_id,
        "insights": insights,
        "new_confidence": new_conf
    }
