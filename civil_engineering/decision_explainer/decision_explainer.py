from civil_engineering.scoring.confidence import calculate_confidence


def explain_decisions(cv, job, intelligence):
    """
    Produces a transparent, weighted explanation of why a CV was adapted
    or skipped for a given job.
    """

    decisions = []

    alignment = intelligence["project_alignment"]
    strength = alignment["strength"]

    weight = (
        0.6 if strength == "strong"
        else 0.45 if strength == "adjacent"
        else 0.3
    )

    reason = (
        "Direct project experience overlap found."
        if strength == "strong"
        else "Relevant adjacent project experience identified."
        if strength == "adjacent"
        else "No direct or adjacent project overlap; CV adapted cautiously."
    )

    seniority = intelligence["seniority"]
    risk_flags = intelligence["risk_flags"]

    # --- Project alignment ---

    decisions.append({
    "type": "project_alignment",
    "strength": alignment["strength"],
    "direct_overlap": alignment.get("direct_overlap", []),
    "adjacent_matches": alignment.get("adjacent_matches", []),
    "adjacency_score": alignment.get("adjacency_score", 0),
    "cv_only_projects": alignment.get("cv_only", []),
    "job_only_projects": alignment.get("job_only", []),
    "weight": weight,
    "reason": reason
})
    
    skill_alignment = intelligence.get("skill_alignment", {})
    skill_score = skill_alignment.get("skill_score", 0)

    if skill_score > 0:
        decisions.append({
            "type": "skill_transferability",
            "score": skill_score,
            "matches": skill_alignment.get("matches", []),
            "weight": 0.2,
            "reason": "Transferable skills identified despite project differences."
        })

    # --- Seniority ---
    decisions.append({
        "type": "seniority_fit",
        "value": seniority,
        "years_required": intelligence["meta"]["years_required"],
        "experience_years": intelligence["meta"]["experience_years"],
        "weight": 0.25,
        "reason": (
            "Experience level matches job expectations."
            if seniority == "matched"
            else f"Candidate is {seniority} for this role."
        )
    })

    # --- Risk (optional, NEVER return early) ---
    if risk_flags:
        decisions.append({
            "type": "risk_assessment",
            "flags": risk_flags,
            "weight": 0.15,
            "reason": "Role involves elevated risk or experience gaps."
        })

    # --- Confidence score (ALWAYS last) ---
    confidence = calculate_confidence(cv, job, intelligence)

    decisions.append({
        "type": "confidence_score",
        **confidence,
        "verdict": (
            "Apply confidently" if confidence["overall_confidence"] >= 70
            else "Apply with caution" if confidence["overall_confidence"] >= 50
            else "Do not apply"
        )
    })

    return decisions


