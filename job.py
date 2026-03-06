# civil_engineering/domain/job.py
#
# ── WHAT THIS IS ─────────────────────────────────────────────────────────────
# A simple data container for a parsed job description.
#
# ── SENIOR DEV CONCEPT: Why a class instead of a dict? ───────────────────────
# You COULD use a plain dict: {"title": "Site Engineer", "years": 3}
# But a class gives you:
#   1. Auto-complete in your editor — job.title, not job["title"]
#   2. A __repr__ so you can print(job) and see something readable
#   3. A place to add methods later (e.g. job.to_dict(), job.is_valid())
#   4. Type hints work — def func(job: ParsedJob) is self-documenting
#
# This class uses __init__ with defaults so every field is optional.
# A parser that can't find the salary just leaves it as None — no crash.

class ParsedJob:
    def __init__(
        self,
        title           = None,
        years_required  = None,
        project_types   = None,
        salary          = None,
        required_skills = None,
        location        = None,
        company         = None,
        raw_text        = None,     # store original text for reference
        apply_email     = None,     # email address to send application to
    ):
        self.title           = title
        self.years_required  = years_required
        self.project_types   = project_types   or []
        self.salary          = salary
        self.required_skills = required_skills or []
        self.location        = location
        self.company         = company
        self.raw_text        = raw_text
        self.apply_email     = apply_email

    def to_dict(self) -> dict:
        """
        Convert to a plain dict — useful when the pipeline needs a dict.

        WHY HAVE THIS METHOD?
        The rest of the pipeline (build_intelligence, adapt_cv etc.) was
        written to work with plain dicts (job.get("title"), job.get("years_required")).
        Rather than rewriting the whole pipeline, we convert to dict at the boundary.
        This is called an "adapter" — a thin translation layer.
        """
        return {
            "title":           self.title,
            "years_required":  self.years_required,
            "project_types":   self.project_types,
            "salary":          self.salary,
            "skills":          self.required_skills,
            "location":        self.location,
            "company":         self.company,
            "raw_text":        self.raw_text,
            "apply_email":      self.apply_email,
        }

    def __repr__(self) -> str:
        return (
            f"ParsedJob("
            f"title={self.title!r}, "
            f"years_required={self.years_required}, "
            f"project_types={self.project_types}, "
            f"salary={self.salary!r}"
            f")"
        )
