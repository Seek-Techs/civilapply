# civil_engineering/guardrails/tracker.py

import json
from pathlib import Path
from datetime import date

TRACKER_FILE = Path("civil_engineering/output/application_tracker.json")


def load_tracker():
    if TRACKER_FILE.exists():
        with open(TRACKER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "date": str(date.today()),
        "applications": []
    }


def save_tracker(tracker):
    TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(tracker, f, indent=2)


def record_application(job):
    tracker = load_tracker()
    tracker["applications"].append({
        "job_title": job.get("job_title"),
        "company": job.get("company"),
        "confidence": job.get("confidence")
    })
    save_tracker(tracker)
