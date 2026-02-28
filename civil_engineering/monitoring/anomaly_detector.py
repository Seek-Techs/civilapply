def detect_anomaly(metrics: dict):
    blocked = metrics.get("applications_blocked", 0)
    attempted = metrics.get("applications_attempted", 0)
    total = blocked + attempted
    runs = metrics.get("total_runs", 0)

    # --- Guard 1: Not enough data ---
    if total < 10:
        return None

    # --- Guard 2: Learning phase ---
    if runs < 5:
        return None

    block_rate = blocked / max(1, total)

    # --- Guard 3: Extreme behavior only ---
    if block_rate > 0.85:
        return {
            "type": "confidence_collapse",
            "message": "Too many jobs blocked — check confidence thresholds."
        }

    return None
