# cv_engine/tailor.py
#
# CV TAILORING — rewrite the candidate's CV summary for a specific job.
#
# TWO MODES:
# 1. rule_based_summary(): works WITHOUT an API key. Uses facts + templates.
#    Good for testing and learning.
# 2. tailor_cv(): calls Claude API. Returns a professionally rewritten summary.
#    Uses the improved prompt from our analysis.
#
# SENIOR DEV: Always build a fallback. If the API is unavailable,
# the pipeline degrades gracefully rather than crashing.

import logging
import json
from typing import Optional

from models import CandidateProfile, JobPosting, MatchResult, SeniorityLevel

logger = logging.getLogger(__name__)


# ── Prompt (the improved version from our analysis) ───────────────────────────

SYSTEM_PROMPT = """You are a senior technical recruiter and CV writing specialist with 15+ years \
placing engineers at infrastructure, construction, and consulting firms. \
You understand ATS systems, hiring manager priorities, and how to highlight \
engineering achievements quantitatively.

STRICT RULES — violating any of these makes the output unusable:
1. Mirror the exact terminology used in the job description — do not paraphrase keywords
2. Quantify achievements where possible (%, scale, duration, value)
3. NEVER invent skills, certifications, or experience not in the source CV
4. NEVER alter company names, job titles, dates, or factual claims
5. Keep the summary under 120 words
6. Return ONLY valid JSON — no markdown fences, no explanation text outside the JSON"""

USER_PROMPT_TEMPLATE = """Tailor the CV summary for this specific job application.

CANDIDATE FACTS (do not change these):
- Name: {name}
- Current Title: {title}
- Total Experience: {total_years} years
- Project Types: {project_types}
- Technical Skills: {skills}
- Matching Experience: {overlap}

JOB BEING APPLIED TO:
- Title: {job_title}
- Company: {company}
- Years Required: {years_required}
- Project Types Needed: {job_projects}

Return this exact JSON structure:
{{
  "summary": "professional CV summary paragraph (max 120 words)",
  "key_skills_to_highlight": ["skill1", "skill2", "skill3"],
  "tailoring_rationale": "one sentence explaining main adaptation made",
  "ats_keywords_used": ["keyword1", "keyword2"]
}}"""


def _build_prompt(
    profile: CandidateProfile,
    job: JobPosting,
    match: MatchResult,
) -> str:
    """Build the user prompt by filling in the template with real data."""
    overlap = profile.project_overlap([pt.value for pt in job.project_types])

    return USER_PROMPT_TEMPLATE.format(
        name=profile.name,
        title=profile.title,
        total_years=profile.total_years,
        project_types=", ".join(profile.project_types) or "General Civil Works",
        skills=", ".join(profile.technical_skills[:8]),  # top 8 skills
        overlap=", ".join(overlap) or "General Civil Works",
        job_title=job.title or "Not specified",
        company=job.company or "Not specified",
        years_required=job.years_required or "Not specified",
        job_projects=", ".join(pt.value for pt in job.project_types) or "Not specified",
    )


def rule_based_summary(
    profile: CandidateProfile,
    job: JobPosting,
    match: MatchResult,
) -> str:
    """
    Generate a CV summary WITHOUT calling any API.
    Uses facts + templates. Less polished, but always works.

    SENIOR DEV: Build the rule-based version FIRST.
    It forces you to understand the logic before adding AI.
    It's also the fallback when the API is unavailable.
    """
    overlap = profile.project_overlap([pt.value for pt in job.project_types])
    projects_text = ", ".join(overlap) if overlap else "civil engineering"

    # Tone adjustments based on seniority match
    if match.seniority == SeniorityLevel.OVERQUALIFIED:
        contribution = (
            "able to contribute immediately in a hands-on, delivery-focused capacity"
        )
    elif match.seniority == SeniorityLevel.JUNIOR:
        contribution = "eager to bring growing expertise and a strong work ethic"
    else:
        contribution = "with a track record of successful project delivery"

    skills_text = ", ".join(profile.technical_skills[:4]) if profile.technical_skills else ""
    skills_line = f" Technical proficiency includes {skills_text}." if skills_text else ""

    summary = (
        f"Experienced {profile.title} with {profile.total_years}+ years delivering "
        f"{projects_text} projects. {contribution.capitalize()}, with a strong "
        f"background in site supervision, QA/QC compliance, and stakeholder coordination."
        f"{skills_line}"
    )

    logger.info("Generated rule-based CV summary for job %s", job.job_id)
    return summary


def tailor_cv(
    profile: CandidateProfile,
    job: JobPosting,
    match: MatchResult,
    api_key: str,
    model: str = "claude-sonnet-4-6",
) -> dict:
    """
    Tailor the CV summary using Claude API.

    Returns a dict with keys:
    - summary: str (the tailored CV summary)
    - key_skills_to_highlight: list[str]
    - tailoring_rationale: str
    - ats_keywords_used: list[str]

    Falls back to rule_based_summary() if API call fails.

    Args:
        profile: Candidate profile
        job:     The job being applied to
        match:   Match result (used for context in the prompt)
        api_key: Anthropic API key
        model:   Which Claude model to use
    """
    if not api_key:
        logger.warning("No API key — using rule-based fallback for job %s", job.job_id)
        return {
            "summary": rule_based_summary(profile, job, match),
            "key_skills_to_highlight": profile.technical_skills[:3],
            "tailoring_rationale": "Rule-based fallback (no API key)",
            "ats_keywords_used": [],
        }

    try:
        import anthropic  # imported here so the module works without the package installed

        client = anthropic.Anthropic(api_key=api_key)
        prompt = _build_prompt(profile, job, match)

        logger.info("Calling Claude %s for CV tailoring (job %s)", model, job.job_id)

        response = client.messages.create(
            model=model,
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text from response
        raw_text = response.content[0].text.strip()

        # Parse JSON — if this fails we fall back to rule-based
        # SENIOR DEV: Never trust LLM output blindly. Always validate.
        result = json.loads(raw_text)

        # Validate required keys exist
        required_keys = {"summary", "key_skills_to_highlight", "tailoring_rationale", "ats_keywords_used"}
        missing = required_keys - set(result.keys())
        if missing:
            raise ValueError(f"LLM response missing keys: {missing}")

        logger.info("CV tailored successfully for job %s", job.job_id)
        return result

    except Exception as e:
        logger.warning(
            "CV tailoring API call failed for job %s: %s. Using rule-based fallback.",
            job.job_id, e
        )
        return {
            "summary": rule_based_summary(profile, job, match),
            "key_skills_to_highlight": profile.technical_skills[:3],
            "tailoring_rationale": f"Fallback (API error: {type(e).__name__})",
            "ats_keywords_used": [],
        }