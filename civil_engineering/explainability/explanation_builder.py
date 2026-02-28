# civil_engineering/explainability/explanation_builder.py

def build_explanation(job, decision, decision_log=None, blocks=None):
    explanation = {
        "job_id": job["job_id"],
        "job_title": job["job_title"],
        "final_decision": decision.get("decision"),
        "confidence": job["confidence"],
        "signals": decision.get("signals", {}),
        "rules_applied": [],
        "blocks": blocks or [],
        "human_override": job.get("human_override"),
    }

    # Optional detailed reasoning
    if decision_log:
        for item in decision_log:
            if item["type"] == "project_alignment":
                explanation["rules_applied"].append(
                    f"Project alignment: {item['strength']}"
                )
            elif item["type"] == "seniority_fit":
                explanation["rules_applied"].append(
                    f"Experience: {item['experience_years']} yrs vs {item['years_required']} yrs"
                )
            elif item["type"] == "confidence_score":
                explanation["rules_applied"].append(
                    f"Confidence score computed as {item['overall_confidence']}%"
                )

    explanation["summary"] = (
        f"{decision.get('decision')} chosen with confidence "
        f"{job['confidence']}% after safety checks."
    )

    return explanation
