# civil_engineering/intelligence/builder.py
#
# ── WHAT THIS FILE DOES ──────────────────────────────────────────────────────
# Takes a CV dict and a job dict, and produces an "intelligence object" —
# a structured summary of HOW WELL the candidate fits the job.
#
# This is NOT scoring. This is SIGNAL EXTRACTION.
# The intelligence object is then consumed by:
#   - scoring/confidence.py  (turns signals into a score)
#   - cv_adapter/adapter.py  (uses signals to tailor CV bullets)
#   - decision_explainer     (uses signals to explain the decision)
#
# ── BUG FIXED: UnboundLocalError on seniority ────────────────────────────────
# ORIGINAL CODE had this structure:
#
#   if experience_years < years_required:
#       seniority = "underqualified"
#   elif abs(experience_years - years_required) <= 2:
#       seniority = "matched"
#   elif experience_years > years_required:
#       if alignment_strength in ["adjacent", "strong"]:
#           seniority = "tolerated_overqualified"
#       else:
#           seniority = "overqualified"
#
# WHAT'S THE BUG?
# Python evaluates conditions top-to-bottom.
# When experience_years == years_required exactly (gap = 0):
#   - First condition: 0 < 0 → False
#   - Second condition: abs(0) <= 2 → True ✓  (this case is fine)
#
# But when experience_years == years_required + 3 (gap = 3):
#   - First condition: False
#   - Second condition: abs(3) <= 2 → False
#   - Third condition: 3 > 0 → True → enters the elif
#   → This case IS handled correctly.
#
# So where does it actually break?
# The elif chain uses `alignment_strength` which is built LATER in the function
# (inside the project_alignment block). If you ever refactor and move code,
# the variable reference breaks. It's also fragile: if `years_required` comes
# in as None (it's optional in some job JSONs), the comparison crashes entirely.
#
# FIX: Add a None guard at the top, and use a cleaner if/elif chain that
# explicitly handles every case including None. No UnboundLocalError possible.

from civil_engineering.intelligence.skill_adjacency import SKILL_ADJACENCY


PROJECT_ADJACENCY = {
    "refinery": {
        "infrastructure": 0.5,
        "industrial": 0.7,
    },
    "infrastructure": {
        "refinery": 0.4,
        "buildings": 0.6,
    },
    "industrial": {
        "refinery": 0.6,
    },
}


def _classify_seniority(experience_years: int, years_required: int | None, alignment_strength: str) -> str:
    """
    Classify seniority as a SEPARATE, NAMED function.

    WHY EXTRACT THIS?
    The original code had this logic embedded mid-function, using a variable
    (`alignment_strength`) that was defined earlier. Extracting it into its own
    function makes the dependency explicit — you HAVE to pass alignment_strength
    in. This is called "making implicit dependencies explicit."

    It also makes this logic independently testable.

    Args:
        experience_years:   candidate's total years
        years_required:     job requirement (can be None)
        alignment_strength: "strong", "adjacent", or "none"

    Returns:
        One of: "underqualified", "matched", "tolerated_overqualified", "overqualified", "unknown"
    """
    # If no years specified, infer from candidate experience and project strength
    # A senior candidate (8+ years) with strong project match = tolerated_overqualified
    # This avoids the job scoring 0 for seniority just because years wasn't in the JD
    if years_required is None:
        if experience_years >= 8 and alignment_strength == "strong":
            return "tolerated_overqualified"
        elif experience_years >= 5:
            return "matched"
        else:
            return "unknown"

    gap = experience_years - years_required

    if gap < 0:
        return "underqualified"

    if abs(gap) <= 2:
        # Within 2 years either side = matched (employers typically tolerate this)
        return "matched"

    # gap > 2: candidate is clearly more experienced than required
    if alignment_strength in ("adjacent", "strong"):
        # If projects align, overqualification is "tolerated" — employer may still consider them
        return "tolerated_overqualified"

    return "overqualified"


def build_intelligence(cv: dict, job: dict) -> dict:
    """
    Extract compatibility signals between a CV and a job.

    Returns an "intelligence object" — a plain dict that downstream
    modules (scoring, cv_adapter, explainer) consume.

    No scoring. No formatting. No decisions. Pure signal extraction.

    Args:
        cv:  Candidate CV dict (as loaded from cv.json)
        job: Job dict (as loaded from jobs/job_NNN.json)

    Returns:
        dict with keys: project_alignment, skill_alignment, seniority, risk_flags, meta
    """

    # ── Extract base values safely ────────────────────────────────────────────
    # .get() with a default means we never crash on missing keys.
    # This is defensive programming — assume the data might be incomplete.
    experience_years = cv.get("profile", {}).get("experience_years", 0)
    years_required   = job.get("years_required")   # intentionally None if missing

    # Normalise to lowercase sets for comparison
    cv_projects  = {p.lower() for p in cv.get("project_types",  [])}
    job_projects = {p.lower() for p in job.get("project_types", [])}

    # ── 1. PROJECT ALIGNMENT ─────────────────────────────────────────────────
    # Direct overlap: candidate HAS experience in what the job NEEDS
    direct_overlap = cv_projects & job_projects

    # Adjacent overlap: no direct match, but related sectors
    # e.g. "industrial" is adjacent to "refinery" with score 0.7
    adjacent_matches = []
    adjacency_score  = 0.0

    if not direct_overlap:
        for job_p in job_projects:
            for cv_p in cv_projects:
                score = PROJECT_ADJACENCY.get(job_p, {}).get(cv_p, 0)
                if score > 0:
                    adjacent_matches.append({
                        "job_project": job_p,
                        "cv_project":  cv_p,
                        "score":       score,
                    })
                    adjacency_score = max(adjacency_score, score)

    # Classify overall alignment strength
    if direct_overlap:
        alignment_strength = "strong"
    elif adjacent_matches:
        alignment_strength = "adjacent"
    else:
        alignment_strength = "none"

    project_alignment = {
        "strength":        alignment_strength,
        "direct_overlap":  sorted(direct_overlap),
        "adjacent_matches": adjacent_matches,
        "adjacency_score": round(adjacency_score, 2),
        "cv_only":         sorted(cv_projects - job_projects),
        "job_only":        sorted(job_projects - cv_projects),
    }

    # ── 2. SKILL ADJACENCY ───────────────────────────────────────────────────
    # Checks if candidate's skills map to job's required skills
    # even when names don't match exactly.
    # e.g. "site supervision" is adjacent to "construction management" (score 0.7)
    cv_skills  = {s.lower() for s in cv.get("skills",  [])}
    job_skills = {s.lower() for s in job.get("skills", [])}

    skill_matches = []
    skill_score   = 0.0

    for cv_skill in cv_skills:
        if cv_skill in job_skills:
            # Exact match
            skill_matches.append({"cv_skill": cv_skill, "job_skill": cv_skill, "score": 1.0})
            skill_score = max(skill_score, 1.0)
        else:
            # Adjacency match
            for job_skill in job_skills:
                adj = SKILL_ADJACENCY.get(cv_skill, {}).get(job_skill, 0)
                if adj > 0:
                    skill_matches.append({"cv_skill": cv_skill, "job_skill": job_skill, "score": adj})
                    skill_score = max(skill_score, adj)

    skill_alignment = {
        "matches":     skill_matches,
        "skill_score": round(skill_score, 2),
    }

    # ── 3. SENIORITY ─────────────────────────────────────────────────────────
    # Now uses the extracted function — no UnboundLocalError possible
    seniority = _classify_seniority(experience_years, years_required, alignment_strength)

    # ── 4. RISK FLAGS ────────────────────────────────────────────────────────
    HIGH_RISK_PROJECTS = {"refinery", "industrial", "oil", "gas"}
    risk_flags = []

    if any(p in HIGH_RISK_PROJECTS for p in job_projects):
        risk_flags.append("high_safety_environment")

    if seniority == "underqualified":
        risk_flags.append("experience_gap")

    # ── 5. ASSEMBLE INTELLIGENCE OBJECT ──────────────────────────────────────
    return {
        "project_alignment": project_alignment,
        "skill_alignment":   skill_alignment,
        "seniority":         seniority,
        "risk_flags":        risk_flags,
        "meta": {
            "years_required":    years_required,
            "experience_years":  experience_years,
        },
    }
