# job_parser/parser.py
#
# PARSING = turning unstructured text into structured data.
# Input:  "We are looking for a Site Engineer with 5+ years..."
# Output: JobPosting(title="Site Engineer", years_required=5, ...)
#
# SENIOR DEV APPROACH:
# 1. Each field has its OWN private function (_extract_*)
# 2. If extraction fails, return None — never crash
# 3. Log what was found
# 4. Each extractor is independently testable

import re
import uuid
import logging
from typing import Optional

from models import JobPosting, ProjectType

# Named logger — never use print() in production code.
# This logger is named "job_parser.parser" (the module path).
# You can control its level independently in logging config.
logger = logging.getLogger(__name__)


# ── Keyword dictionaries ──────────────────────────────────────────────────────
# DATA at the top, LOGIC in functions below.
# To add a new role: add one line here. No logic changes.

ROLE_KEYWORDS: dict[str, list[str]] = {
    "Civil / Structural Engineer": ["civil / structural", "civil structural"],
    "Site Engineer":               ["site engineer"],
    "Civil Engineer":              ["civil engineer"],
    "Structural Engineer":         ["structural engineer"],
    "Project Manager":             ["project manager"],
    "Quantity Surveyor":           ["quantity surveyor"],
}

PROJECT_KEYWORDS: dict[ProjectType, list[str]] = {
    ProjectType.INFRASTRUCTURE: ["infrastructure", "road", "bridge", "drainage", "highway"],
    ProjectType.BUILDINGS:      ["building", "commercial"],
    ProjectType.INDUSTRIAL:     ["industrial", "plant", "factory", "refinery"],
    ProjectType.WATER_SEWAGE:   ["sewage", "treatment plant", "water treatment"],
    ProjectType.RESIDENTIAL:    ["residential", "housing", "apartment"],
    ProjectType.ENERGY:         ["energy", "solar", "wind farm", "power station"],
}


# ── Private helpers (one per field) ──────────────────────────────────────────

def _extract_title(text: str) -> Optional[str]:
    """Extract job title. Tries longer (more specific) patterns first."""
    text_lower = text.lower()
    # Sort by keyword length descending so "Civil / Structural" matches before "Civil"
    sorted_roles = sorted(
        ROLE_KEYWORDS.items(),
        key=lambda kv: len(kv[1][0]),
        reverse=True
    )
    for role, patterns in sorted_roles:
        for pattern in patterns:
            if pattern in text_lower:
                logger.debug("Title matched: %r", role)
                return role
    return None


def _extract_years(text: str) -> Optional[int]:
    """
    Extract minimum years of experience.
    "5-8 years" -> 5 (lower bound = minimum to qualify)
    "5+ years"  -> 5
    """
    # Range: "5-8 years" or "5–8 years"
    match = re.search(r"(\d+)\s*[-\u2013to]+\s*(\d+)\s*years", text, re.IGNORECASE)
    if match:
        return int(match.group(1))  # lower bound

    # Single: "5 years" or "5+ years"
    match = re.search(r"(\d+)\+?\s+years", text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    return None


def _extract_project_types(text: str) -> list[ProjectType]:
    """Find all project types mentioned. Returns list (jobs can have multiple)."""
    text_lower = text.lower()
    found = set()
    for project_type, keywords in PROJECT_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                found.add(project_type)
                break  # one match per type is enough
    return list(found)


def _extract_salary(text: str) -> tuple[Optional[int], Optional[int]]:
    """
    Extract salary range. Returns (min, max).
    SENIOR DEV: Functions returning multiple values use tuples.
    Unpack: min_sal, max_sal = _extract_salary(text)
    """
    # "£35,000 - £45,000"
    match = re.search(r"£([\d,]+)\s*[-\u2013]\s*£([\d,]+)", text)
    if match:
        return (
            int(match.group(1).replace(",", "")),
            int(match.group(2).replace(",", "")),
        )
    # "35k-45k"
    match = re.search(r"(\d+)k\s*[-\u2013]\s*(\d+)k", text, re.IGNORECASE)
    if match:
        return int(match.group(1)) * 1000, int(match.group(2)) * 1000

    return None, None


# ── Public API ────────────────────────────────────────────────────────────────

def parse_job_description(text: str, job_id: Optional[str] = None) -> JobPosting:
    """
    Parse raw job description text into a structured JobPosting.

    SENIOR DEV PATTERN: The public function is SIMPLE.
    It calls helpers and assembles the result.
    All complexity lives in _extract_* helpers.

    Args:
        text:   Raw job description text
        job_id: Stable ID. A random UUID is generated if not provided.

    Returns:
        JobPosting with all extractable fields populated. Missing fields = None.

    Raises:
        ValueError: if text is empty
    """
    if not text or not text.strip():
        raise ValueError("Job description text cannot be empty")

    effective_id = job_id or str(uuid.uuid4())
    salary_min, salary_max = _extract_salary(text)

    job = JobPosting(
        job_id=effective_id,
        title=_extract_title(text),
        years_required=_extract_years(text),
        project_types=_extract_project_types(text),
        salary_min=salary_min,
        salary_max=salary_max,
        raw_text=text,
    )

    logger.info(
        "Parsed job %s: title=%r years=%s projects=%s",
        effective_id, job.title, job.years_required,
        [p.value for p in job.project_types]
    )
    return job