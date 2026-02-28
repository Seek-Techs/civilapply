def calculate_confidence(cv, job, intelligence):
    score = 0
    breakdown = {}

    # ==========================================================
    # 1. PROJECT ALIGNMENT (Direct + Adjacent)
    # ==========================================================
    project_alignment = intelligence.get("project_alignment", {})
    strength = project_alignment.get("strength", "none")
    adjacency_score = project_alignment.get("adjacency_score", 0)

    if strength == "strong":
        project_points = 40
    elif strength == "adjacent":
        project_points = int(adjacency_score * 40)  # partial credit
    else:
        project_points = 0

    score += project_points
    breakdown["project_alignment"] = project_points

    # ==========================================================
    # 2. SENIORITY (Tolerance-aware)
    # ==========================================================
    seniority = intelligence.get("seniority")

    if seniority == "matched":
        seniority_points = 30
    elif seniority == "tolerated_overqualified":
        seniority_points = 20
    elif seniority == "overqualified":
        seniority_points = 15
    else:  # underqualified
        seniority_points = 0

    score += seniority_points
    breakdown["seniority_fit"] = seniority_points

    # ==========================================================
    # 3. SKILL TRANSFERABILITY (A3.3)
    # ==========================================================
    skill_alignment = intelligence.get("skill_alignment", {})
    skill_score = skill_alignment.get("skill_score", 0)

    skills_points = int(skill_score * 30)  # max 30
    score += skills_points
    breakdown["skills_match"] = skills_points

    # ==========================================================
    # 4. RISK PENALTIES
    # ==========================================================
    risk_penalty = 0
    risk_flags = intelligence.get("risk_flags", [])

    if "high_safety_environment" in risk_flags:
        risk_penalty -= 15
    if "experience_gap" in risk_flags:
        risk_penalty -= 20

    score += risk_penalty
    breakdown["risk_penalty"] = risk_penalty

    # ==========================================================
    # FINAL
    # ==========================================================
    return {
        "overall_confidence": max(score, 0),
        "breakdown": breakdown
    }
