# civil_engineering/apply_strategy/strategy_engine.py

def decide_apply_strategy(job):
    confidence = job.get("confidence", 0)

    decision_signals = {
        "confidence": confidence,
        "rank": job.get("rank"),
        "risk_flags": job.get("risk_flags", [])
    }

    if confidence >= 70:
        return {
            "decision": "auto_apply",
            "platform": "linkedin",
            "reason": "High confidence match (>= 70)",
            "signals": decision_signals
        }

    if confidence >= 50:
        return {
            "decision": "strategic_review",
            "platform": None,
            "reason": "Moderate confidence — requires human review",
            "signals": decision_signals
        }

    return {
        "decision": "reject",
        "platform": None,
        "reason": "Low confidence (< 50)",
        "signals": decision_signals
    }
