# matcher/engine.py
#
# THE MATCHING ENGINE — scores candidate fit against a job.
#
# SENIOR DEV PRINCIPLES:
# 1. PURE FUNCTIONS: no database, no API, no files. Same in -> same out.
# 2. SINGLE RESPONSIBILITY: each _score_* function does ONE dimension.
# 3. PARTIAL SCORING: real scores between 0 and max, not just 0 or full.
# 4. RICH RETURN: MatchResult object with full breakdown, not just a number.

import logging
from models import CandidateProfile, JobPosting, MatchResult, SeniorityLevel
from config import AppConfig

logger = logging.getLogger(__name__)


# ── Dimension scorers ─────────────────────────────────────────────────────────
# Each returns (score: float, reason: str)
# score is between 0 and max_points
# reason is a human-readable explanation (used in cover letters + audit log)

def _score_role(profile: CandidateProfile, job: JobPosting, max_pts: int) -> tuple[float, str]:
    """Score role title match. Full / half / zero."""
    if not job.title:
        return max_pts * 0.5, "Job title unspecified — partial credit"

    job_lower = job.title.lower()

    # Check desired roles first
    for role in profile.desired_roles:
        if role.lower() in job_lower or job_lower in role.lower():
            return float(max_pts), f"Role match: {role!r} = {job.title!r}"

    # Check current title
    if profile.title.lower() in job_lower:
        return float(max_pts), f"Current title matches: {profile.title!r}"

    # Partial: shared words (ignoring stop words)
    stops = {"and", "the", "of", "a", "an", "/", "senior", "junior"}
    p_words = set(profile.title.lower().split()) - stops
    j_words = set(job_lower.split()) - stops
    common = p_words & j_words
    if common:
        return max_pts * 0.5, f"Partial role match (shared words: {common})"

    return 0.0, f"No role match: {profile.title!r} vs {job.title!r}"


def _score_experience(profile: CandidateProfile, job: JobPosting, max_pts: int) -> tuple[float, str]:
    """Score years of experience. Full / proportional."""
    if job.years_required is None:
        return max_pts * 0.7, "No experience requirement — partial credit"

    if profile.total_years >= job.years_required:
        return float(max_pts), (
            f"Experience met: {profile.total_years} yrs >= {job.years_required} required"
        )

    shortfall = job.years_required - profile.total_years
    if shortfall <= 1:
        return max_pts * 0.75, f"Close: {profile.total_years} yrs, {shortfall} yr short"

    # Proportional: candidate has 3 of 5 required → 60%
    ratio = profile.total_years / job.years_required
    return max_pts * max(ratio, 0.0), (
        f"Under: {profile.total_years} of {job.years_required} yrs"
    )


def _score_projects(profile: CandidateProfile, job: JobPosting, max_pts: int) -> tuple[float, str]:
    """Score project type overlap. Proportional to coverage."""
    if not job.project_types:
        return max_pts * 0.6, "No project types specified — partial credit"

    job_types = [pt.value for pt in job.project_types]
    overlap = profile.project_overlap(job_types)

    if not overlap:
        return 0.0, (
            f"No project overlap. Candidate: {profile.project_types}. Job: {job_types}"
        )

    coverage = len(overlap) / len(job_types)
    return max_pts * coverage, f"Project match ({coverage:.0%}): {overlap}"


def _classify_seniority(profile: CandidateProfile, job: JobPosting) -> SeniorityLevel:
    """How senior is the candidate relative to the job requirement?"""
    if job.years_required is None:
        return SeniorityLevel.UNKNOWN
    gap = profile.total_years - job.years_required
    if gap >= 5:  return SeniorityLevel.OVERQUALIFIED
    if gap >= 2:  return SeniorityLevel.SENIOR
    if gap >= 0:  return SeniorityLevel.MID
    return SeniorityLevel.JUNIOR


# ── Public API ────────────────────────────────────────────────────────────────

def match_candidate_to_job(
    profile: CandidateProfile,
    job: JobPosting,
    config: AppConfig,
) -> MatchResult:
    """
    Match candidate to job. Returns full MatchResult.

    THIS FUNCTION IS PURE:
    - No database, no API calls, no file I/O
    - Same inputs always produce same output
    - Easy to unit test, thread-safe, fast

    Args:
        profile: The candidate's profile
        job:     The parsed job posting
        config:  App config (contains weights and thresholds)

    Returns:
        MatchResult with score breakdown and text explanations
    """
    cfg = config.matching

    role_score,  role_reason  = _score_role(profile, job, cfg.weight_role_match)
    exp_score,   exp_reason   = _score_experience(profile, job, cfg.weight_experience)
    proj_score,  proj_reason  = _score_projects(profile, job, cfg.weight_projects)

    total = role_score + exp_score + proj_score
    qualified = total >= cfg.auto_apply_threshold
    seniority = _classify_seniority(profile, job)

    # Identify best and worst dimension for CV tailoring hints
    dims = {
        "role":       (role_score,  cfg.weight_role_match, role_reason),
        "experience": (exp_score,   cfg.weight_experience, exp_reason),
        "projects":   (proj_score,  cfg.weight_projects,   proj_reason),
    }
    # Ratio = what fraction of maximum did we achieve per dimension?
    ratios = {k: v[0] / v[1] if v[1] > 0 else 0 for k, v in dims.items()}
    best  = max(ratios, key=ratios.get)
    worst = min(ratios, key=ratios.get)

    logger.info(
        "[%s] total=%.1f (role=%.1f exp=%.1f proj=%.1f) qualified=%s seniority=%s",
        job.job_id, total, role_score, exp_score, proj_score, qualified, seniority.value
    )

    return MatchResult(
        job_id=job.job_id,
        total_score=round(total, 1),
        qualified=qualified,
        score_role_match=round(role_score, 1),
        score_experience=round(exp_score, 1),
        score_projects=round(proj_score, 1),
        seniority=seniority,
        reasons=[role_reason, exp_reason, proj_reason],
        top_strength=dims[best][2],
        top_gap=dims[worst][2],
    )