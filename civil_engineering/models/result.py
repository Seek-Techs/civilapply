# models/result.py
#
# Results are ALSO models.
# Keeping results as typed dataclasses means:
# - The pipeline always knows exactly what it receives from each stage
# - Tests can assert on specific fields, not just "did it work"
# - Adding a new field later is one line, not scattered edits

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from .job import SeniorityLevel


class ApplicationOutcome(str, Enum):
    """
    What happened after submitting? Feeds back to improve future matching.
    
    SENIOR DEV CONCEPT: Feedback loops.
    A naive system applies and forgets.
    A smart system tracks outcomes and adjusts scoring over time.
    """
    APPLIED = "applied"
    SHORTLISTED = "shortlisted"
    INTERVIEWED = "interviewed"
    REJECTED = "rejected"
    GHOSTED = "ghosted"
    OFFER_RECEIVED = "offer_received"


@dataclass
class MatchResult:
    """
    Output of matching one candidate against one job.

    ORIGINAL returned: {"score": 72.5, "qualified": True, "reasons": [...]}
    OUR VERSION adds:
    - dimension_scores: WHERE did the score come from? (transparency)
    - seniority: is candidate overqualified / underqualified?
    - top_strength / top_gap: what to highlight in CV and cover letter
    """
    job_id: str
    total_score: float
    qualified: bool

    score_role_match: float = 0.0
    score_experience: float = 0.0
    score_projects: float = 0.0

    seniority: SeniorityLevel = SeniorityLevel.UNKNOWN
    reasons: list[str] = field(default_factory=list)
    top_strength: Optional[str] = None
    top_gap: Optional[str] = None
    confidence: float = 1.0     # 0-1; low if job description was sparse


@dataclass
class ApplicationDecision:
    """
    Final decision: should we apply? Includes tailored CV and cover letter.

    Separate from MatchResult because the decision involves more than score:
    - Daily/weekly application limits (guardrails)
    - Strategic jobs (worth applying despite lower score)
    - Human override
    """
    job_id: str
    should_apply: bool
    reason: str

    match_result: Optional[MatchResult] = None
    cv_summary: Optional[str] = None
    cover_letter: Optional[str] = None

    # Audit trail — senior devs always track WHO decided WHAT
    decided_by: str = "ai"              # "ai" or "human_override"
    outcome: Optional[ApplicationOutcome] = None