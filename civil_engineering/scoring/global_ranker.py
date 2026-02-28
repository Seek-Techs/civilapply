import json
from pathlib import Path


OUTPUT_DIR = Path("civil_engineering/output")


def build_global_ranking():
    """
    Aggregates job_summary.json files into a global ranked list.
    """

    results = []

    for job_dir in OUTPUT_DIR.iterdir():
        if not job_dir.is_dir():
            continue

        summary_file = job_dir / "job_summary.json"
        if not summary_file.exists():
            continue

        with open(summary_file, "r", encoding="utf-8") as f:
            summary = json.load(f)

        results.append(summary)

    # Sort by confidence (highest first)
    results.sort(key=lambda x: x.get("confidence", 0), reverse=True)

    # Assign global rank
    for idx, job in enumerate(results, start=1):
        job["global_rank"] = idx

    return results


def write_global_outputs(ranking):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # JSON output
    with open(OUTPUT_DIR / "global_ranking.json", "w", encoding="utf-8") as f:
        json.dump(ranking, f, indent=2)

    # CSV output (simple, no pandas)
    csv_lines = ["global_rank,job_id,job_title,confidence,rank,recommended_action,verdict"]

    for job in ranking:
        csv_lines.append(
            f"{job.get('global_rank')},"
            f"{job.get('job_id')},"
            f"{job.get('job_title')},"
            f"{job.get('confidence')},"
            f"{job.get('rank')},"
            f"{job.get('recommended_action')},"
            f"{job.get('verdict')}"
        )

    with open(OUTPUT_DIR / "global_ranking.csv", "w", encoding="utf-8") as f:
        f.write("\n".join(csv_lines))


def generate_global_ranking(output_dir: Path):
    """
    Aggregates approved jobs into a global ranking list.
    """

    ranked_jobs = []

    for job_dir in output_dir.iterdir():
        review_file = job_dir / "review_packet.json"

        if not review_file.exists():
            continue

        with open(review_file, "r", encoding="utf-8") as f:
            packet = json.load(f)

        if packet.get("human_decision") != "approve":
            continue

        ranked_jobs.append({
            "job_id": packet["job_id"],
            "job_title": packet["job_title"],
            "confidence": packet["confidence"],
            "rank": packet["rank"],
            "recommended_action": packet["recommended_action"]
        })

    ranked_jobs.sort(
        key=lambda x: x["confidence"],
        reverse=True
    )

    return ranked_jobs