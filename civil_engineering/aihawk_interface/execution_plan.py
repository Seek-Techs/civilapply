# civil_engineering/aihawk_interface/execution_plan.py

def build_execution_plan(job_summary, strategy):
    """
    Converts strategy decision into executable instructions.
    """

    if strategy["decision"] == "skip":
        return None

    return {
        "job_id": job_summary["job_id"],
        "job_title": job_summary["job_title"],
        "platform": strategy["platform"],
        "cv_variant": strategy["cv_variant"],
        "action": strategy["decision"],
        "confidence": job_summary["confidence"]
    }
