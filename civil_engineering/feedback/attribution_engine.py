def attribute_outcome(job, decision_log, outcome):
    """
    Links outcomes back to decision signals.
    """
    insights = []

    confidence = next(
        d for d in decision_log if d["type"] == "confidence_score"
    )

    if outcome in ["shortlisted", "interviewed", "offer"]:
        insights.append({
            "signal": "confidence_model",
            "effect": "positive",
            "confidence": confidence["overall_confidence"]
        })

    if outcome == "rejected":
        insights.append({
            "signal": "confidence_model",
            "effect": "negative",
            "confidence": confidence["overall_confidence"]
        })

    return insights
