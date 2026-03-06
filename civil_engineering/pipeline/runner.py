# pipeline/runner.py
#
# THE PIPELINE ORCHESTRATOR
# Connects all the pieces: parse -> match -> tailor -> decide
#
# SENIOR DEV PATTERN: "Pipeline / Chain of Responsibility"
# Each stage does ONE thing and passes its output to the next.
# The orchestrator only CONNECTS stages — it contains no business logic itself.
#
# This makes it easy to:
# - Add a new stage (just insert it in the right place)
# - Skip a stage (just comment it out or add a flag)
# - Test each stage independently

import logging
import json
import os
from datetime import datetime
from pathlib import Path

from models import CandidateProfile, JobPosting, ApplicationDecision
from matcher import match_candidate_to_job
from cv_engine import tailor_cv
from config import AppConfig

logger = logging.getLogger(__name__)


def process_one_job(
    profile: CandidateProfile,
    job: JobPosting,
    config: AppConfig,
) -> ApplicationDecision:
    """
    Run the full pipeline for ONE job.

    Stages:
    1. Match: score the candidate against the job
    2. Gate:  if score too low, return early (don't waste API call on tailoring)
    3. Tailor: rewrite CV summary for this specific job
    4. Decide: make the final yes/no application decision

    Args:
        profile: Candidate profile
        job:     Parsed job posting
        config:  App configuration

    Returns:
        ApplicationDecision with should_apply, tailored CV, and full audit trail
    """
    logger.info("Processing job %s: %r at %r", job.job_id, job.title, job.company)

    # ── Stage 1: Match ────────────────────────────────────────────────────────
    match = match_candidate_to_job(profile, job, config)

    # ── Stage 2: Gate ─────────────────────────────────────────────────────────
    # SENIOR DEV: "Fail fast" — return early if we can, saves time and API cost
    if match.total_score < config.matching.review_threshold:
        logger.info("Job %s rejected: score %.1f < threshold %.1f",
                    job.job_id, match.total_score, config.matching.review_threshold)
        return ApplicationDecision(
            job_id=job.job_id,
            should_apply=False,
            reason=f"Score too low: {match.total_score:.1f}/100. Gap: {match.top_gap}",
            match_result=match,
        )

    # ── Stage 3: CV Tailoring ─────────────────────────────────────────────────
    tailor_result = tailor_cv(
        profile=profile,
        job=job,
        match=match,
        api_key=config.anthropic_api_key,
        model=config.llm_model_quality,
    )
    cv_summary = tailor_result.get("summary", "")

    # ── Stage 4: Decision ─────────────────────────────────────────────────────
    if match.qualified:
        decision = ApplicationDecision(
            job_id=job.job_id,
            should_apply=True,
            reason=f"Score {match.total_score:.1f}/100. Strength: {match.top_strength}",
            match_result=match,
            cv_summary=cv_summary,
        )
    else:
        # Score is between review_threshold and auto_apply_threshold
        # Flag for human review rather than auto-applying
        decision = ApplicationDecision(
            job_id=job.job_id,
            should_apply=False,  # won't auto-apply, but flags for review
            reason=(
                f"Score {match.total_score:.1f}/100 — above review threshold but below "
                f"auto-apply threshold. Flagged for human review."
            ),
            match_result=match,
            cv_summary=cv_summary,
            decided_by="review_flagged",
        )

    return decision


def process_all_jobs(
    profile: CandidateProfile,
    jobs: list[JobPosting],
    config: AppConfig,
    save_output: bool = True,
) -> list[ApplicationDecision]:
    """
    Run the pipeline across ALL jobs. Returns ranked list of decisions.

    SENIOR DEV: This is where you'd add async/parallel processing later.
    For now it runs sequentially — simple and correct first, fast later.

    Args:
        profile:     Candidate profile
        jobs:        List of parsed job postings
        config:      App configuration
        save_output: If True, saves results to output directory

    Returns:
        List of ApplicationDecision, sorted by match score (highest first)
    """
    logger.info("Starting pipeline: %d jobs for %s", len(jobs), profile.name)

    decisions = []
    for job in jobs:
        try:
            decision = process_one_job(profile, job, config)
            decisions.append(decision)
        except Exception as e:
            # SENIOR DEV: Never let one job failure kill the whole pipeline
            logger.error("Pipeline failed for job %s: %s", job.job_id, e, exc_info=True)

    # Sort: apply=True first, then by score descending
    decisions.sort(
        key=lambda d: (
            d.should_apply,
            d.match_result.total_score if d.match_result else 0
        ),
        reverse=True
    )

    logger.info(
        "Pipeline complete. %d/%d jobs qualify for application.",
        sum(1 for d in decisions if d.should_apply),
        len(decisions)
    )

    if save_output:
        _save_results(decisions, config.output_dir)

    return decisions


def _save_results(decisions: list[ApplicationDecision], output_dir: str) -> None:
    """
    Save all decisions to a JSON output file.

    SENIOR DEV: Output is always JSON so it can be:
    - Read by other tools
    - Committed to git for audit trail
    - Loaded into a database later
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(output_dir) / f"results_{timestamp}.json"

    output = []
    for d in decisions:
        record = {
            "job_id": d.job_id,
            "should_apply": d.should_apply,
            "reason": d.reason,
            "decided_by": d.decided_by,
            "cv_summary": d.cv_summary,
        }
        if d.match_result:
            record["match"] = {
                "total_score": d.match_result.total_score,
                "qualified": d.match_result.qualified,
                "seniority": d.match_result.seniority.value,
                "score_role": d.match_result.score_role_match,
                "score_experience": d.match_result.score_experience,
                "score_projects": d.match_result.score_projects,
                "top_strength": d.match_result.top_strength,
                "top_gap": d.match_result.top_gap,
                "reasons": d.match_result.reasons,
            }
        output.append(record)

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    logger.info("Results saved to %s", output_path)