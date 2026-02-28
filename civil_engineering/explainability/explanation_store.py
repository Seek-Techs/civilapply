# civil_engineering/explainability/explanation_store.py

import json
from pathlib import Path
from datetime import datetime

STORE = Path("civil_engineering/output/decision_explanations.json")


def store_explanation(explanation: dict):
    STORE.parent.mkdir(parents=True, exist_ok=True)

    if STORE.exists():
        data = json.loads(STORE.read_text())
    else:
        data = []

    explanation["timestamp"] = datetime.utcnow().isoformat()
    data.append(explanation)

    STORE.write_text(json.dumps(data, indent=2))


def load_explanations():
    if not STORE.exists():
        return []
    return json.loads(STORE.read_text())
