from civil_engineering.normalization.signal_maps import PROJECT_SIGNAL_MAP, RISK_SIGNAL_MAP, SKILL_SIGNAL_MAP


def normalize_signals(cv):
    normalized = {
        "project_types": set(),
        "skills": set(),
        "risk_flags": set()
    }

    text_blocks = []

    # collect signal text
    for exp in cv.get("experience", []):
        text_blocks.append(exp.get("role", "").lower())
        for b in exp.get("bullets", []):
            text_blocks.append(b.lower())

    for skill in cv.get("skills", []):
        text_blocks.append(skill.lower())

    # --- Project normalization ---
    for text in text_blocks:
        for key, projects in PROJECT_SIGNAL_MAP.items():
            if key in text:
                normalized["project_types"].update(projects)

    # --- Skill normalization ---
    for text in text_blocks:
        for key, skills in SKILL_SIGNAL_MAP.items():
            if key in text:
                normalized["skills"].update(skills)

    # --- Risk normalization ---
    for project in normalized["project_types"]:
        if project in RISK_SIGNAL_MAP:
            normalized["risk_flags"].add(RISK_SIGNAL_MAP[project])

    return {
        "project_types": sorted(normalized["project_types"]),
        "skills": sorted(normalized["skills"]),
        "risk_flags": sorted(normalized["risk_flags"])
    }
