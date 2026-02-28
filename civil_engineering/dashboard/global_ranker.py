import json
from pathlib import Path


OUTPUT_DIR = Path("civil_engineering/output")


def build_global_ranking():
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

    rank_order = {
        "A": 1,
        "B": 2,
        "C": 3,
        "rejected": 4
    }

    jobs.sort(
        key=lambda x: (
            rank_order.get(x["rank"], 5),
            -(x.get("confidence") or 0)
        )
    )

    output_file = OUTPUT_DIR / "global_job_ranking.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2)

    print(f"📊 Global ranking written to {output_file}")


if __name__ == "__main__":
    build_global_ranking()
