import json
from pathlib import Path
from datetime import datetime

STORE = Path("civil_engineering/output/human_overrides.json")


def record_human_override(job_id, decision, reason, signals):
    STORE.parent.mkdir(parents=True, exist_ok=True)

    if STORE.exists():
        with open(STORE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = []

    data.append({
        "job_id": job_id,
        "decision": decision,
        "reason": reason,
        "signals": signals,
        "timestamp": datetime.utcnow().isoformat()
    })

    with open(STORE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
