# import json
# from pathlib import Path
# from datetime import datetime

# OUTCOME_FILE = Path("civil_engineering/output/application_outcomes.json")


# def record_outcome(job_id, outcome, notes=None):
#     record = {
#         "job_id": job_id,
#         "outcome": outcome,
#         "notes": notes,
#         "timestamp": datetime.utcnow().isoformat()
#     }

#     if OUTCOME_FILE.exists():
#         data = json.loads(OUTCOME_FILE.read_text())
#     else:
#         data = []

#     data.append(record)
#     OUTCOME_FILE.write_text(json.dumps(data, indent=2))


# civil_engineering/feedback/outcome_store.py

import json
from pathlib import Path
from datetime import datetime

STORE = Path("civil_engineering/output/outcomes.json")


def record_outcome(job_id: str, outcome: str, notes: str = ""):
    STORE.parent.mkdir(parents=True, exist_ok=True)

    if STORE.exists():
        with open(STORE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}

    data[job_id] = {
        "outcome": outcome,
        "notes": notes,
        "timestamp": datetime.utcnow().isoformat()
    }

    with open(STORE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_outcomes():
    """
    Load all recorded outcomes indexed by job_id.
    """
    if not STORE.exists():
        return {}

    with open(STORE, "r", encoding="utf-8") as f:
        return json.load(f)
