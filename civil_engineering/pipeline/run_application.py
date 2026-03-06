# import json
# from pathlib import Path

# from civil_engineering.cv_adapter.adapter import adapt_cv
# from civil_engineering.intelligence.builder import build_intelligence
# from civil_engineering.decision_explainer import explain_decisions
# from civil_engineering.eligibility.job_filter import is_job_relevant
# from civil_engineering.scoring.job_ranker import rank_job
# from civil_engineering.scoring.global_ranker import build_global_ranking, write_global_outputs
# from civil_engineering.normalization.signal_normalizer import normalize_signals
# from civil_engineering.normalization.normalize_cv import normalize_cv





# BASE_DIR = Path("civil_engineering")
# DATA_DIR = BASE_DIR / "data"
# JOBS_DIR = DATA_DIR / "jobs"
# OUTPUT_DIR = BASE_DIR / "output"


# def main():
#     # 1. Load base CV
#     with open(DATA_DIR / "cv.json", "r", encoding="utf-8") as f:
#         cv = json.load(f)

#     # 2. Iterate through job files
#     for job_file in JOBS_DIR.glob("*.json"):
#         job_id = job_file.stem
#         print(f"\n▶ Processing {job_id}")

#         with open(job_file, "r", encoding="utf-8") as f:
#             job = json.load(f)

#         job_output_dir = OUTPUT_DIR / job_id
#         job_output_dir.mkdir(parents=True, exist_ok=True)

#         # 🔒 Eligibility gate
#         is_relevant, reason = is_job_relevant(cv, job)

#         if not is_relevant:
#             print(f"⏭ Skipped {job_id}: {reason}")

#             skip_log = {
#                 "status": "skipped",
#                 "job_id": job_id,
#                 "job_title": job.get("title"),
#                 "reason": reason,
#                 "years_required": job.get("years_required"),
#                 "project_types": job.get("project_types"),
#                 "recommendation": "Do not apply"
#             }

#             with open(job_output_dir / "skip_log.json", "w", encoding="utf-8") as f:
#                 json.dump(skip_log, f, indent=2)

#             with open(job_output_dir / "job_summary.json", "w", encoding="utf-8") as f:
#                 json.dump({
#                     "job_id": job_id,
#                     "job_title": job.get("title"),
#                     "confidence": 0,
#                     "rank": "rejected",
#                     "recommended_action": "do_not_apply",
#                     "verdict": "Skipped by eligibility filter"
#                 }, f, indent=2)

#             continue

#         # 3. Build intelligence
#         cv = normalize_cv(cv)
#         intelligence = build_intelligence(cv, job)

#         # 4. Adapt CV
#         adapted_cv = adapt_cv(cv, job, intelligence)

#         # 5. Explain decisions
#         decision_explanations = explain_decisions(cv, job, intelligence)

#         confidence_block = extract_confidence(decision_explanations)

#         ranking = (
#             rank_job(confidence_block["overall_confidence"])
#             if confidence_block
#             else {"rank": "unknown", "action": "manual_review"}
#         )

#         # 6. Write core outputs
#         with open(job_output_dir / "adapted_cv.json", "w", encoding="utf-8") as f:
#             json.dump(adapted_cv, f, indent=2)

#         with open(job_output_dir / "decision_log.json", "w", encoding="utf-8") as f:
#             json.dump(decision_explanations, f, indent=2)

#         # 7. Job summary (machine-readable)
#         with open(job_output_dir / "job_summary.json", "w", encoding="utf-8") as f:
#             json.dump({
#                 "job_id": job_id,
#                 "job_title": job.get("title"),
#                 "confidence": confidence_block["overall_confidence"] if confidence_block else None,
#                 "rank": ranking["rank"],
#                 "recommended_action": ranking["action"],
#                 "verdict": confidence_block["verdict"] if confidence_block else "Undetermined"
#             }, f, indent=2)

#         # 🧠 8. HUMAN-IN-THE-LOOP REVIEW PACKET
#         with open(job_output_dir / "review_packet.json", "w", encoding="utf-8") as f:
#             json.dump({
#                 "job_id": job_id,
#                 "job_title": job.get("title"),
#                 "confidence": confidence_block["overall_confidence"] if confidence_block else None,
#                 "rank": ranking["rank"],
#                 "recommended_action": ranking["action"],
#                 "decision_summary": {
#                     "project_alignment": intelligence.get("project_alignment", {}).get("strength"),
#                     "seniority_fit": intelligence.get("seniority"),
#                     "risk_flags": intelligence.get("risk_flags", [])
#                 },
#                 "human_decision": None,
#                 "approved_at": None
#             }, f, indent=2)

#         print(f"✔ Finished {job_id}")
#     # 9. Global ranking across all jobs
#     global_ranking = build_global_ranking()
#     write_global_outputs(global_ranking)


#     print("\n✅ Batch CV adaptation completed.")


# def extract_confidence(decisions):
#     for item in decisions:
#         if item.get("type") == "confidence_score":
#             return item
#     return None


# if __name__ == "__main__":
#     main()



# civil_engineering/pipeline/run_application.py
#
# ── THE MAIN PIPELINE ORCHESTRATOR ───────────────────────────────────────────
# This is the entry point for batch CV adaptation.
# It loads one CV and many jobs, then runs the full pipeline for each job.
#
# ── BUG FIXED: CV Mutation inside the loop ───────────────────────────────────
# ORIGINAL CODE (simplified):
#
#   cv = json.load(...)           # load CV once
#   for job_file in JOBS_DIR:
#       cv = normalize_cv(cv)     # ← BUG: cv is REASSIGNED on every iteration
#       intelligence = build_intelligence(cv, job)
#
# WHY IS THIS A BUG?
# normalize_cv() adds fields to the CV dict (project_types, skills, risk_flags).
# On the FIRST iteration, it normalises the original CV → fine.
# On the SECOND iteration, it normalises the ALREADY-NORMALISED CV.
# Fields keep accumulating. By job 3, the CV has different data than what was loaded.
#
# This is called "mutating shared state" — a classic bug when looping.
# The fix is two lines:
#   1. Normalise the CV ONCE before the loop
#   2. Deep-copy the normalised CV inside the loop so each job gets a fresh copy
#
# ── SENIOR DEV CONCEPT: copy.deepcopy() ──────────────────────────────────────
# Python dicts are passed by REFERENCE, not by value.
# This means: if you do `adapted_cv = cv`, and then modify adapted_cv,
# you also modify cv — they point to the SAME object in memory.
#
# cv = {"skills": ["Excel"]}
# adapted_cv = cv
# adapted_cv["skills"].append("PowerBI")
# print(cv["skills"])  # ["Excel", "PowerBI"] ← cv was mutated!
#
# deepcopy() creates a completely independent copy — changes to the copy
# never affect the original.

import json
import copy
from pathlib import Path

from civil_engineering.cv_adapter.adapter import adapt_cv
from civil_engineering.intelligence.builder import build_intelligence
from civil_engineering.decision_explainer import explain_decisions
from civil_engineering.eligibility.job_filter import is_job_relevant
from civil_engineering.scoring.job_ranker import rank_job
from civil_engineering.scoring.global_ranker import build_global_ranking, write_global_outputs
from civil_engineering.normalization.signal_normalizer import normalize_signals
from civil_engineering.normalization.normalize_cv import normalize_cv


BASE_DIR   = Path("civil_engineering")
DATA_DIR   = BASE_DIR / "data"
JOBS_DIR   = DATA_DIR / "jobs"
OUTPUT_DIR = BASE_DIR / "output"


def main():
    # ── 1. Load CV ────────────────────────────────────────────────────────────
    with open(DATA_DIR / "cv.json", "r", encoding="utf-8") as f:
        raw_cv = json.load(f)

    # ── 2. Normalise CV ONCE (outside the loop) ───────────────────────────────
    #
    # WHY OUTSIDE THE LOOP?
    # Normalisation enriches the CV with inferred project types and skills.
    # It should run exactly once on the original data.
    # Running it repeatedly (inside the loop) would snowball the CV's fields.
    #
    # We keep `base_cv` as the normalised reference, never mutating it.
    base_cv = normalize_cv(raw_cv)

    # ── 3. Process each job ───────────────────────────────────────────────────
    for job_file in sorted(JOBS_DIR.glob("*.json")):
        job_id = job_file.stem
        print(f"\n▶ Processing {job_id}")

        with open(job_file, "r", encoding="utf-8") as f:
            job = json.load(f)

        job_output_dir = OUTPUT_DIR / job_id
        job_output_dir.mkdir(parents=True, exist_ok=True)

        # ── Eligibility gate ──────────────────────────────────────────────────
        # Fast rejection before spending compute on intelligence + adaptation.
        # "Fail fast" principle: detect the obvious No early.
        is_relevant, reason = is_job_relevant(base_cv, job)

        if not is_relevant:
            print(f"  ⏭ Skipped: {reason}")
            _write_skip_outputs(job_output_dir, job_id, job, reason)
            continue

        # ── Per-job CV copy ───────────────────────────────────────────────────
        # deepcopy ensures each job's adaptation is independent.
        # Without this, changes made by adapt_cv() for job_001 would persist
        # into job_002's processing.
        cv = copy.deepcopy(base_cv)

        # ── Intelligence extraction ───────────────────────────────────────────
        intelligence = build_intelligence(cv, job)

        # ── CV adaptation ─────────────────────────────────────────────────────
        adapted_cv = adapt_cv(cv, job, intelligence)

        # ── Decision explanation ──────────────────────────────────────────────
        decision_explanations = explain_decisions(cv, job, intelligence)
        confidence_block = _extract_confidence(decision_explanations)

        ranking = (
            rank_job(confidence_block["overall_confidence"])
            if confidence_block
            else {"rank": "unknown", "action": "manual_review", "requires_human_review": True}
        )

        # ── Write outputs ─────────────────────────────────────────────────────
        _write_job_outputs(
            job_output_dir, job_id, job,
            adapted_cv, decision_explanations,
            confidence_block, ranking,
            intelligence,
        )

        print(f"  ✔ Done — confidence: {confidence_block.get('overall_confidence') if confidence_block else 'N/A'}  rank: {ranking['rank']}")

    # ── 4. Global ranking across all jobs ─────────────────────────────────────
    global_ranking = build_global_ranking()
    write_global_outputs(global_ranking)
    print("\n✅ Batch processing complete.")


# ── Helper functions ──────────────────────────────────────────────────────────
#
# WHY EXTRACT THESE?
# The main() function above tells you WHAT happens at a high level.
# Helper functions tell you HOW each step works in detail.
# This is called "two levels of abstraction" — the top tells the story,
# the bottom handles the details. Readers can skim main() and drill in
# to any helper they need.

def _write_skip_outputs(job_output_dir: Path, job_id: str, job: dict, reason: str):
    """Write minimal outputs for a job that was rejected at the eligibility gate."""
    skip_log = {
        "status": "skipped",
        "job_id": job_id,
        "job_title": job.get("title"),
        "reason": reason,
        "years_required": job.get("years_required"),
        "project_types": job.get("project_types"),
        "recommendation": "Do not apply",
    }
    _write_json(job_output_dir / "skip_log.json", skip_log)
    _write_json(job_output_dir / "job_summary.json", {
        "job_id": job_id,
        "job_title": job.get("title"),
        "confidence": 0,
        "rank": "rejected",
        "recommended_action": "do_not_apply",
        "verdict": "Skipped by eligibility filter",
    })


def _write_job_outputs(
    job_output_dir: Path,
    job_id: str,
    job: dict,
    adapted_cv: dict,
    decision_explanations: list,
    confidence_block: dict | None,
    ranking: dict,
    intelligence: dict,
):
    """Write all output files for a successfully processed job."""
    _write_json(job_output_dir / "adapted_cv.json",    adapted_cv)
    _write_json(job_output_dir / "decision_log.json",  decision_explanations)

    confidence_value = confidence_block["overall_confidence"] if confidence_block else None
    verdict          = confidence_block.get("verdict")         if confidence_block else "Undetermined"

    _write_json(job_output_dir / "job_summary.json", {
        "job_id":              job_id,
        "job_title":           job.get("title"),
        "confidence":          confidence_value,
        "rank":                ranking["rank"],
        "recommended_action":  ranking["action"],
        "verdict":             verdict,
    })

    _write_json(job_output_dir / "review_packet.json", {
        "job_id":             job_id,
        "job_title":          job.get("title"),
        "confidence":         confidence_value,
        "rank":               ranking["rank"],
        "recommended_action": ranking["action"],
        "decision_summary": {
            "project_alignment": intelligence.get("project_alignment", {}).get("strength"),
            "seniority_fit":     intelligence.get("seniority"),
            "risk_flags":        intelligence.get("risk_flags", []),
        },
        "human_decision": None,      # filled in later by a human reviewer
        "approved_at":    None,
    })


def _extract_confidence(decisions: list) -> dict | None:
    """Find the confidence_score block in a list of decision explanations."""
    for item in decisions:
        if item.get("type") == "confidence_score":
            return item
    return None


def _write_json(path: Path, data):
    """Write a dict to a JSON file. Single place to change encoding/indent settings."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()