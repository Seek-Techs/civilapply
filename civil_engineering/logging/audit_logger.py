import json
from datetime import datetime
from pathlib import Path

AUDIT_LOG = Path("civil_engineering/output/audit_log.jsonl")

def log_event(event_type, payload):
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event": event_type,
        "payload": payload
    }

    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
