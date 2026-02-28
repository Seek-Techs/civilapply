from civil_engineering.normalization.signal_maps import (
    PROJECT_SIGNAL_MAP,
    SKILL_SIGNAL_MAP,
    RISK_SIGNAL_MAP
)


def normalize_cv(cv):
    project_types = set(cv.get("project_types", []))
    skills = set(cv.get("skills", []))

    text = []

    for exp in cv.get("experience", []):
        text.append(exp.get("role", "").lower())
        for b in exp.get("bullets", []):
            text.append(b.lower())

    for t in text:
        for key, values in PROJECT_SIGNAL_MAP.items():
            if key in t:
                project_types.update(values)

        for key, values in SKILL_SIGNAL_MAP.items():
            if key in t:
                skills.update(values)

    # Risk flags based on project types
    risk_flags = set()  
    for project in project_types:
        if project in RISK_SIGNAL_MAP:
            risk_flags.add(RISK_SIGNAL_MAP[project])

    cv["project_types"] = sorted(project_types)
    cv["skills"] = sorted(skills)
    cv["risk_flags"] = sorted(risk_flags)

    return cv
