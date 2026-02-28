# civil_engineering/cv_adapter/cv_builder.py

from cv_adapter.bullet_rewriter import rewrite_bullets
from cv_adapter.bullet_ranker import rank_bullets

MAX_BULLETS = 5


def build_cv_bullets(raw_bullets, profile, job, intelligence):
    """
    Assemble final CV bullets using strict rules.
    """

    # 1. Rewrite bullets (safe language, safety-aware)
    rewritten = rewrite_bullets(
        raw_bullets,
        profile=profile,
        job=job,
        intelligence=intelligence
    )

    # 2. Rank bullets by relevance
    ranked = rank_bullets(rewritten, intelligence)

    # 3. Seniority masking rule
    if intelligence.get("seniority") == "overqualified":
        ranked = deprioritize_leadership(ranked)

    # 4. Enforce bullet cap
    final_bullets = ranked[:MAX_BULLETS]

    return final_bullets


def deprioritize_leadership(bullets):
    """
    Push leadership-heavy bullets lower.
    """
    leadership_terms = ["led", "managed", "headed", "directed"]

    def is_leadership(bullet):
        return any(term in bullet.lower() for term in leadership_terms)

    hands_on = [b for b in bullets if not is_leadership(b)]
    leadership = [b for b in bullets if is_leadership(b)]

    return hands_on + leadership
