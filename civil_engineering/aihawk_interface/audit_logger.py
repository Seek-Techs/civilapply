import json
from datetime import datetime
from pathlib import Path

AUDIT_FILE = Path("civil_engineering/output/execution_audit.json")


def log_execution(record: dict):
    record["timestamp"] = datetime.utcnow().isoformat()

    if AUDIT_FILE.exists():
        with open(AUDIT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = []

    data.append(record)

    with open(AUDIT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
