# civil_engineering/cv_adapter/test_cv_builder.py

def test_cv_builder_flow():
    raw_bullets = [
        "- Led refinery shutdown activities",
        "- Supervised workers on buildings projects",
        "- Supported industrial site reporting",
        "- Coordinated site inspections",
    ]

    profile = {"experience_years": 11}

    job = {
        "project_types": ["Buildings"]
    }

    intelligence = {
        "seniority": "overqualified",
        "emphasize": ["buildings"],
        "neutral": ["industrial"],
        "downplay": ["refinery"],
        "risk_flags": ["high_safety_environment"]
    }

    from cv_adapter.cv_builder import build_cv_bullets

    final = build_cv_bullets(raw_bullets, profile, job, intelligence)

    assert len(final) <= 5
    assert "buildings" in final[0].lower()
