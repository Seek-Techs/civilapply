import json
from datetime import datetime
from pathlib import Path


OUTPUT_DIR = Path("civil_engineering/output")


def update_human_decision(job_id, decision):
    """
    Updates human decision for a job review packet.
    decision: approve | reject | defer
    """

    job_dir = OUTPUT_DIR / job_id
    review_file = job_dir / "review_packet.json"

    if not review_file.exists():
        raise FileNotFoundError(f"No review packet found for {job_id}")

    with open(review_file, "r", encoding="utf-8") as f:
        review = json.load(f)

    review["human_decision"] = decision
    review["approved_at"] = datetime.utcnow().isoformat()

    with open(review_file, "w", encoding="utf-8") as f:
        json.dump(review, f, indent=2)

    return review
if __name__ == "__main__":
    # Example usage
    job_id = "job_001"
    decision = "approve"  # or "reject" or "defer"
    updated_review = update_human_decision(job_id, decision)
    print(f"Updated review for {job_id}: {updated_review}")
