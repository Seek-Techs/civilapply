from pathlib import Path
import json
from datetime import datetime

METRICS_FILE = Path("civil_engineering/output/metrics.json")

DEFAULT_METRICS = {
    "total_runs": 0,
    "applications_attempted": 0,
    "applications_blocked": 0,
    "auto_apply_count": 0,
    "strategic_review_count": 0,
    "last_run": None
}


def load_metrics():
    if METRICS_FILE.exists():
        return json.loads(METRICS_FILE.read_text())
    return DEFAULT_METRICS.copy()


def save_metrics(metrics):
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    METRICS_FILE.write_text(json.dumps(metrics, indent=2))


def update_metrics(update_fn):
    metrics = load_metrics()
    update_fn(metrics)
    metrics["last_run"] = datetime.utcnow().isoformat()
    save_metrics(metrics)
