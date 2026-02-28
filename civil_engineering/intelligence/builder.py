from civil_engineering.intelligence.skill_adjacency import SKILL_ADJACENCY


PROJECT_ADJACENCY = {
    "refinery": {
        "infrastructure": 0.5,
        "industrial": 0.7
    },
    "infrastructure": {
        "refinery": 0.4,
        "buildings": 0.6
    },
    "industrial": {
        "refinery": 0.6
    }
}


def build_intelligence(cv, job):
    """
    Extracts deterministic signals about CV ↔ Job compatibility.
    No decisions. No filtering. No formatting.
    """

    # --- Base values ---
    experience_years = cv.get("profile", {}).get("experience_years", 0)
    years_required = job.get("years_required", 0)

    cv_projects = set(p.lower() for p in cv.get("project_types", []))
    job_projects = set(p.lower() for p in job.get("project_types", []))

    # ==========================================================
    # 1. PROJECT ALIGNMENT (direct + adjacency)
    # ==========================================================
    direct_overlap = cv_projects & job_projects
    adjacent_matches = []
    adjacency_score = 0.0

    if not direct_overlap:
        for job_p in job_projects:
            for cv_p in cv_projects:
                score = PROJECT_ADJACENCY.get(job_p, {}).get(cv_p, 0)
                if score > 0:
                    adjacent_matches.append({
                        "job_project": job_p,
                        "cv_project": cv_p,
                        "score": score
                    })
                    adjacency_score = max(adjacency_score, score)

    if direct_overlap:
        alignment_strength = "strong"
    elif adjacent_matches:
        alignment_strength = "adjacent"
    else:
        alignment_strength = "none"

    project_alignment = {
        "strength": alignment_strength,
        "direct_overlap": sorted(list(direct_overlap)),
        "adjacent_matches": adjacent_matches,
        "adjacency_score": round(adjacency_score, 2),
        "cv_only": sorted(list(cv_projects - job_projects)),
        "job_only": sorted(list(job_projects - cv_projects))
    }

    # ==========================================================
    # 2. SKILL ADJACENCY & TRANSFERABILITY (A3.3)
    # ==========================================================
    cv_skills = set(s.lower() for s in cv.get("skills", []))
    job_skills = set(s.lower() for s in job.get("skills", []))

    skill_matches = []
    skill_score = 0.0

    for cv_skill in cv_skills:
        if cv_skill in job_skills:
            skill_matches.append({
                "cv_skill": cv_skill,
                "job_skill": cv_skill,
                "score": 1.0
            })
            skill_score = max(skill_score, 1.0)
        else:
            for job_skill in job_skills:
                adj_score = SKILL_ADJACENCY.get(cv_skill, {}).get(job_skill, 0)
                if adj_score > 0:
                    skill_matches.append({
                        "cv_skill": cv_skill,
                        "job_skill": job_skill,
                        "score": adj_score
                    })
                    skill_score = max(skill_score, adj_score)

    skill_alignment = {
        "matches": skill_matches,
        "skill_score": round(skill_score, 2)
    }

    # ==========================================================
    # 3. SENIORITY (A3.2 – tolerance-aware)
    # ==========================================================
    if experience_years < years_required:
        seniority = "underqualified"
    elif abs(experience_years - years_required) <= 2:
        seniority = "matched"
    elif experience_years > years_required:
        if alignment_strength in ["adjacent", "strong"]:
            seniority = "tolerated_overqualified"
        else:
            seniority = "overqualified"

    # ==========================================================
    # 4. RISK FLAGS
    # ==========================================================
    risk_flags = []
    high_risk_projects = {"refinery", "industrial", "oil", "gas"}

    if any(p in high_risk_projects for p in job_projects):
        risk_flags.append("high_safety_environment")

    if seniority == "underqualified":
        risk_flags.append("experience_gap")

    # ==========================================================
    # 5. FINAL INTELLIGENCE OBJECT
    # ==========================================================
    return {
        "project_alignment": project_alignment,
        "skill_alignment": skill_alignment,
        "seniority": seniority,
        "risk_flags": risk_flags,
        "meta": {
            "years_required": years_required,
            "experience_years": experience_years
        }
    }
