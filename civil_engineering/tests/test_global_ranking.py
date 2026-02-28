from pathlib import Path
from civil_engineering.scoring.global_ranker import generate_global_ranking


def test_global_ranking_only_approved_jobs():
    output_dir = Path("civil_engineering/output")

    ranking = generate_global_ranking(output_dir)

    assert isinstance(ranking, list)

    for job in ranking:
        assert "job_id" in job
        assert "confidence" in job
        assert job["confidence"] > 0


def test_global_ranking_sorted_descending():
    output_dir = Path("civil_engineering/output")

    ranking = generate_global_ranking(output_dir)

    confidences = [job["confidence"] for job in ranking]

    assert confidences == sorted(confidences, reverse=True)
