import json
from pathlib import Path
from civil_engineering.aihawk_interface.rules import (
    MIN_CONFIDENCE,
    ALLOWED_ACTIONS,
    BLOCKED_RANKS
)

OUTPUT_DIR = Path("civil_engineering/output")


def load_global_ranking():
    path = OUTPUT_DIR / "global_ranking.json"
    if not path.exists():
        raise FileNotFoundError("global_ranking.json not found")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def select_jobs_for_application():
    jobs = load_global_ranking()
    approved = []

    for job in jobs:
        if job["confidence"] < MIN_CONFIDENCE:
            continue

        if job["rank"] in BLOCKED_RANKS:
            continue

        if job["recommended_action"] not in ALLOWED_ACTIONS:
            continue

        approved.append(job)

    return approved
