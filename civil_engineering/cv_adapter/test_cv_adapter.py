# cv_adapter/test_cv_adapter.py
from civil_engineering.cv_adapter.bullet_ranker import rank_bullets

def test_bullet_ranking_basic():
    bullets = [
        "- Coordinated refinery shutdown activities",
        "- Supervised workers on buildings projects",
        "- Supported industrial site reporting",
    ]

    intelligence = {
        "emphasize": ["buildings"],
        "neutral": ["industrial"],
        "downplay": ["refinery"],
    }

    ranked = rank_bullets(bullets, intelligence)

    assert len(ranked) == 3
    assert "buildings" in ranked[0].lower()
    assert "industrial" in ranked[1].lower()
    assert "refinery" in ranked[2].lower()

if __name__ == "__main__":
    test_bullet_ranking_basic()
    print("test_bullet_ranking_basic PASSED")
