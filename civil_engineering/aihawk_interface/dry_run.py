import json
from pathlib import Path

BASE_DIR = Path("civil_engineering")
OUTPUT_DIR = BASE_DIR / "output"
GLOBAL_RANKING_FILE = OUTPUT_DIR / "global_job_ranking.json"


def load_global_ranking():
    if not GLOBAL_RANKING_FILE.exists():
        raise FileNotFoundError(
            "Global ranking file not found. Run the global ranking step first."
        )

    with open(GLOBAL_RANKING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def select_jobs_for_application(global_ranking):
    auto_apply = []
    strategic_review = []

    for job in global_ranking:
        if job["rank"] == "strong_fit":
            auto_apply.append(job)
        elif job["rank"] == "strategic_fit":
            strategic_review.append(job)

    return auto_apply, strategic_review


if __name__ == "__main__":
    global_ranking = load_global_ranking()

    auto_apply, strategic_review = select_jobs_for_application(global_ranking)

    print("\nAIHawk DRY RUN — AUTO APPLY")
    if not auto_apply:
        print("No jobs qualified for auto application.")
    else:
        for job in auto_apply:
            print(f"- {job['job_title']} ({job['confidence']}%)")

    print("\nAIHawk DRY RUN — STRATEGIC REVIEW REQUIRED")
    if not strategic_review:
        print("No jobs require strategic review.")
    else:
        for job in strategic_review:
            print(f"- {job['job_title']} ({job['confidence']}%) → HUMAN REVIEW")
