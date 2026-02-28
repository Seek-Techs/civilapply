import datetime
import json
from pathlib import Path
from civil_engineering.feedback.signal_hashing import hash_signal_bucket


DECISION_LOG = Path("civil_engineering/output/decision_log.json")


def store_decision(job_id, signals):
    if DECISION_LOG.exists():
        data = json.loads(DECISION_LOG.read_text())
    else:
        data = {}

    data[job_id] = signals
    data["signal_bucket"] = hash_signal_bucket(signals)
    data["timestamp"] = datetime.utcnow().isoformat()
    DECISION_LOG.write_text(json.dumps(data, indent=2))
