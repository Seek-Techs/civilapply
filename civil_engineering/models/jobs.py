# models/job.py
#
# WHY ENUMS instead of plain strings?
#
# ORIGINAL: job["project_types"] = ["Infrastructure", "Buildings"]
# Problem: "infrastructure" (lowercase) != "Infrastructure" -> silent mismatch
# Problem: "Infrastructur" (typo) -> valid Python, wrong behaviour
#
# WITH Enum:
#   ProjectType.INFRASTRUCTURE -> auto-complete, typo detection, exact comparison
#   ProjectType("infrastructure") -> raises ValueError immediately if invalid

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ProjectType(str, Enum):
    """
    Valid project types. Inheriting from str means:
    ProjectType.BUILDINGS == "Buildings" is True.
    This lets us compare enums and strings from JSON freely.
    """
    BUILDINGS = "Buildings"
    INFRASTRUCTURE = "Infrastructure"
    INDUSTRIAL = "Industrial"
    WATER_SEWAGE = "Water & Sewage"
    RESIDENTIAL = "Residential"
    COMMERCIAL = "Commercial"
    ENERGY = "Energy"


class SeniorityLevel(str, Enum):
    """How senior is the candidate relative to the job requirement?"""
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    OVERQUALIFIED = "overqualified"
    UNKNOWN = "unknown"


@dataclass
class JobPosting:
    """
    A parsed job posting. All fields are Optional because job descriptions
    vary wildly — some omit salary, some omit years required, etc.
    We never crash because a field is missing; we handle None gracefully.
    """
    job_id: str
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    years_required: Optional[int] = None
    project_types: list[ProjectType] = field(default_factory=list)
    required_skills: list[str] = field(default_factory=list)

    source_url: Optional[str] = None
    raw_text: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None

    is_eligible: Optional[bool] = None
    eligibility_reason: Optional[str] = None

    def salary_display(self) -> str:
        if self.salary_min and self.salary_max:
            return f"£{self.salary_min:,} – £{self.salary_max:,}"
        if self.salary_min:
            return f"From £{self.salary_min:,}"
        if self.salary_max:
            return f"Up to £{self.salary_max:,}"
        return "Not specified"