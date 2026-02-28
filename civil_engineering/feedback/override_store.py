import json
from pathlib import Path
from datetime import datetime

OVERRIDE_FILE = Path("civil_engineering/output/human_overrides.json")


def record_override(job_id: str, override_type: str, notes: str = ""):
    """
    override_type:
      - force_apply
      - force_skip
      - platform_change
    """
    record = {
        "job_id": job_id,
        "override_type": override_type,
        "notes": notes,
        "timestamp": datetime.utcnow().isoformat()
    }

    data = []
    if OVERRIDE_FILE.exists():
        data = json.loads(OVERRIDE_FILE.read_text())

    data.append(record)
    OVERRIDE_FILE.write_text(json.dumps(data, indent=2))


def load_overrides():
    if not OVERRIDE_FILE.exists():
        return []
    return json.loads(OVERRIDE_FILE.read_text())
