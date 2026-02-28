def generate_explanation(job, decision):
    confidence = job.get("confidence", 0)
    rank = job.get("rank")
    skills = job.get("skills", [])
    risk_flags = job.get("risk_flags", [])

    explanation = {
        "summary": "",
        "details": []
    }

    if decision["decision"] == "auto_apply":
        explanation["summary"] = "Auto-applied due to strong match."
        explanation["details"].extend([
            f"Confidence score: {confidence}",
            f"Job rank: {rank}",
            "No critical risk flags detected"
        ])

    elif decision["decision"] == "strategic_review":
        explanation["summary"] = "Held for human review."
        explanation["details"].extend([
            f"Moderate confidence score: {confidence}",
            "Potential skill overlap but uncertainty remains"
        ])

    else:
        explanation["summary"] = "Rejected due to low confidence."
        explanation["details"].extend([
            f"Confidence score too low: {confidence}",
            "Insufficient alignment with profile"
        ])

    if risk_flags:
        explanation["details"].append(
            f"Risk flags present: {', '.join(risk_flags)}"
        )

    return explanation
