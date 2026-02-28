# civil_engineering/cv_adapter/adapter.py

from civil_engineering.cv_adapter.bullet_rewriter import rewrite_bullets
from civil_engineering.cv_adapter.bullet_ranker import rank_bullets
from civil_engineering.cv_adapter.skill_weighting import weight_skills


def adapt_cv(cv_json, job, intelligence):
    """
    Core CV adaptation orchestrator
    """

    adapted_cv = cv_json.copy()

    # 1. Adapt experience bullets
    for role in adapted_cv.get("experience", []):
        bullets = role.get("bullets", [])

        rewritten = rewrite_bullets(
            bullets=bullets,
            profile=cv_json.get("profile", {}),
            job=job,
            intelligence=intelligence,
        )

        ranked = rank_bullets(rewritten, intelligence)

        role["bullets"] = ranked

    # 2. Adapt skills
    adapted_cv["skills"] = weight_skills(
        adapted_cv.get("skills", []),
        intelligence,
    )

    return adapted_cv
