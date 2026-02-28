# civil_engineering/cv_variants/structured.py

def build_structured_cv(cv):
    """
    ATS-friendly CV format.
    """
    return {
        "profile": cv["profile"],
        "skills": sorted(cv.get("skills", [])),
        "experience": cv.get("experience", [])
    }
