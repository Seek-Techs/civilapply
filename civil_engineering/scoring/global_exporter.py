import json
import csv
from pathlib import Path


OUTPUT_DIR = Path("civil_engineering/output")


def load_job_summaries():
    jobs = []

    for job_dir in OUTPUT_DIR.iterdir():
        if not job_dir.is_dir():
            continue

        summary_file = job_dir / "job_summary.json"
        if not summary_file.exists():
            continue

        with open(summary_file, "r", encoding="utf-8") as f:
            summary = json.load(f)

        jobs.append(summary)

    return jobs


def export_global_ranking():
    jobs = load_job_summaries()

    # Sort by confidence DESC
    jobs_sorted = sorted(
        jobs,
        key=lambda x: x.get("confidence", 0),
        reverse=True
    )

    # --- JSON export ---
    json_path = OUTPUT_DIR / "global_ranking.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(jobs_sorted, f, indent=2)

    # --- CSV export ---
    csv_path = OUTPUT_DIR / "global_ranking.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "job_id",
                "job_title",
                "confidence",
                "rank",
                "recommended_action",
                "verdict"
            ]
        )
        writer.writeheader()
        writer.writerows(jobs_sorted)

    return json_path, csv_path
