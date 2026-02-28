import json
from pathlib import Path

from civil_engineering.cv_adapter.adapter import adapt_cv
from civil_engineering.intelligence.builder import build_intelligence
from civil_engineering.decision_explainer import explain_decisions
from civil_engineering.eligibility.job_filter import is_job_relevant
from civil_engineering.scoring.job_ranker import rank_job
from civil_engineering.scoring.global_ranker import build_global_ranking, write_global_outputs
from civil_engineering.normalization.signal_normalizer import normalize_signals
from civil_engineering.normalization.normalize_cv import normalize_cv





BASE_DIR = Path("civil_engineering")
DATA_DIR = BASE_DIR / "data"
JOBS_DIR = DATA_DIR / "jobs"
OUTPUT_DIR = BASE_DIR / "output"


def main():
    # 1. Load base CV
    with open(DATA_DIR / "cv.json", "r", encoding="utf-8") as f:
        cv = json.load(f)

    # 2. Iterate through job files
    for job_file in JOBS_DIR.glob("*.json"):
        job_id = job_file.stem
        print(f"\n▶ Processing {job_id}")

        with open(job_file, "r", encoding="utf-8") as f:
            job = json.load(f)

        job_output_dir = OUTPUT_DIR / job_id
        job_output_dir.mkdir(parents=True, exist_ok=True)

        # 🔒 Eligibility gate
        is_relevant, reason = is_job_relevant(cv, job)

        if not is_relevant:
            print(f"⏭ Skipped {job_id}: {reason}")

            skip_log = {
                "status": "skipped",
                "job_id": job_id,
                "job_title": job.get("title"),
                "reason": reason,
                "years_required": job.get("years_required"),
                "project_types": job.get("project_types"),
                "recommendation": "Do not apply"
            }

            with open(job_output_dir / "skip_log.json", "w", encoding="utf-8") as f:
                json.dump(skip_log, f, indent=2)

            with open(job_output_dir / "job_summary.json", "w", encoding="utf-8") as f:
                json.dump({
                    "job_id": job_id,
                    "job_title": job.get("title"),
                    "confidence": 0,
                    "rank": "rejected",
                    "recommended_action": "do_not_apply",
                    "verdict": "Skipped by eligibility filter"
                }, f, indent=2)

            continue

        # 3. Build intelligence
        cv = normalize_cv(cv)
        intelligence = build_intelligence(cv, job)

        # 4. Adapt CV
        adapted_cv = adapt_cv(cv, job, intelligence)

        # 5. Explain decisions
        decision_explanations = explain_decisions(cv, job, intelligence)

        confidence_block = extract_confidence(decision_explanations)

        ranking = (
            rank_job(confidence_block["overall_confidence"])
            if confidence_block
            else {"rank": "unknown", "action": "manual_review"}
        )

        # 6. Write core outputs
        with open(job_output_dir / "adapted_cv.json", "w", encoding="utf-8") as f:
            json.dump(adapted_cv, f, indent=2)

        with open(job_output_dir / "decision_log.json", "w", encoding="utf-8") as f:
            json.dump(decision_explanations, f, indent=2)

        # 7. Job summary (machine-readable)
        with open(job_output_dir / "job_summary.json", "w", encoding="utf-8") as f:
            json.dump({
                "job_id": job_id,
                "job_title": job.get("title"),
                "confidence": confidence_block["overall_confidence"] if confidence_block else None,
                "rank": ranking["rank"],
                "recommended_action": ranking["action"],
                "verdict": confidence_block["verdict"] if confidence_block else "Undetermined"
            }, f, indent=2)

        # 🧠 8. HUMAN-IN-THE-LOOP REVIEW PACKET
        with open(job_output_dir / "review_packet.json", "w", encoding="utf-8") as f:
            json.dump({
                "job_id": job_id,
                "job_title": job.get("title"),
                "confidence": confidence_block["overall_confidence"] if confidence_block else None,
                "rank": ranking["rank"],
                "recommended_action": ranking["action"],
                "decision_summary": {
                    "project_alignment": intelligence.get("project_alignment", {}).get("strength"),
                    "seniority_fit": intelligence.get("seniority"),
                    "risk_flags": intelligence.get("risk_flags", [])
                },
                "human_decision": None,
                "approved_at": None
            }, f, indent=2)

        print(f"✔ Finished {job_id}")
    # 9. Global ranking across all jobs
    global_ranking = build_global_ranking()
    write_global_outputs(global_ranking)


    print("\n✅ Batch CV adaptation completed.")


def extract_confidence(decisions):
    for item in decisions:
        if item.get("type") == "confidence_score":
            return item
    return None


if __name__ == "__main__":
    main()
