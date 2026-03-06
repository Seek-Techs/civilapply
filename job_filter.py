# civil_engineering/eligibility/job_filter.py
#
# ── WHAT THIS FILE DOES ──────────────────────────────────────────────────────
# Decides whether a pasted job is relevant to a civil engineer.
# This is the FIRST gate — if a job fails here we stop immediately.
#
# ── THE BUG WE FIXED ─────────────────────────────────────────────────────────
# The original logic checked project_type overlap BEFORE checking for
# non-engineering signals. So an events job that contained the word "bridge"
# (used metaphorically: "bridge between the team") got tagged as
# Infrastructure, passed the overlap check, and was never rejected.
#
# FIX: Check non-engineering signals FIRST. If the job is clearly in the
# wrong industry, reject it immediately — don't even look at project types.
# Order of checks matters. Most restrictive check goes first.
#
# ── SENIOR DEV CONCEPT: "Order of guards matters" ────────────────────────────
# Guard clauses should go from most-certain to least-certain.
# "This is an events company" is more certain than "this has infrastructure keywords"
# so it must be checked first.

NON_ENGINEERING_SIGNALS = {
    "event production", "event management", "event design",
    "wedding", "décor", "decoration company", "styling",
    "hospitality", "catering", "fashion", "retail", "restaurant",
    "marketing agency", "advertising", "entertainment company",
    "media production", "event specialist",
}

CIVIL_ENGINEERING_SIGNALS = {
    "site engineer", "civil engineer", "structural engineer",
    "project engineer", "resident engineer", "quantity surveyor",
    "construction", "infrastructure", "structural works",
    "site supervision", "setting out", "concrete", "drainage",
    "reinforced concrete", "earthworks", "piling", "formwork",
    "road construction", "bridge construction", "highway",
    "hse", "qa/qc", "cdm", "smsts", "cscs",
}


def is_job_relevant(cv: dict, job: dict, raw_text: str = "") -> tuple[bool, str]:
    """
    Determine whether a job is relevant to a civil engineering profile.

    Check order (most certain first):
      0. CV industry check — if CV is not civil engineering, reject immediately
      1. Non-engineering industry signals in raw text → reject immediately
      2. Civil engineering signals in raw text → accept
      3. Project type overlap between CV and job → accept
      4. Engineering keywords in job title → accept
      5. Default → reject with explanation
    """
    text_lower = raw_text.lower() if raw_text else ""

    # ── Check 0: CV industry gate (most important for multi-user tool) ────────
    # If the uploaded CV is clearly not civil engineering, reject before
    # wasting time on job matching — and show a clear message.
    try:
        from civil_engineering.cv_reader import detect_cv_industry
        industry = detect_cv_industry(cv)
        if not industry['is_civil'] and industry['confidence'] >= 50:
            detected = industry.get('detected', 'non-civil')
            return False, (
                f"Your uploaded CV appears to be a {detected.replace('_', ' ')} CV, "
                f"not a civil engineering CV. "
                f"CivilApply is designed for civil/structural/infrastructure engineers. "
                f"Please upload a civil engineering CV to generate applications."
            )
    except Exception:
        pass  # If detection fails, continue normally

    # ── Check 1: Non-engineering industry (FIRST — most certain) ─────────────
    # Using multi-word phrases avoids false matches.
    # "event" alone would match "civil engineering event" but
    # "event production" or "event management" only matches actual events jobs.
    if text_lower:
        non_eng_hits = [kw for kw in NON_ENGINEERING_SIGNALS if kw in text_lower]
        eng_hits     = [kw for kw in CIVIL_ENGINEERING_SIGNALS if kw in text_lower]

        if non_eng_hits and not eng_hits:
            # Clear non-engineering signals with no civil engineering signals
            sample = non_eng_hits[:3]
            return False, (
                f"This appears to be a {non_eng_hits[0].split()[0]} industry role, "
                f"not civil engineering. "
                f"Keywords detected: {', '.join(sample)}. "
                f"This tool is built for civil/structural/infrastructure roles."
            )

    # ── Check 2: Civil engineering signals in raw text ────────────────────────
    if text_lower:
        eng_hits = [kw for kw in CIVIL_ENGINEERING_SIGNALS if kw in text_lower]
        if len(eng_hits) >= 2:
            return True, f"Civil engineering role confirmed ({len(eng_hits)} signals found)"

    # ── Check 3: Project type overlap ─────────────────────────────────────────
    cv_domain  = {p.lower() for p in cv.get("project_types", [])}
    job_domain = {p.lower() for p in job.get("project_types", [])}
    overlap    = cv_domain & job_domain

    if overlap:
        return True, f"Project type overlap: {', '.join(overlap)}"

    # ── Check 4: Engineering in job title ─────────────────────────────────────
    job_title = (job.get("title") or "").lower()
    eng_titles = {"engineer", "surveyor", "construction", "site manager", "infrastructure"}
    if any(word in job_title for word in eng_titles):
        return True, f"Engineering role based on job title: {job.get('title')}"

    return False, (
        "Job does not appear to be in civil/structural/infrastructure engineering. "
        "If this is wrong, the job description may use unusual terminology."
    )
