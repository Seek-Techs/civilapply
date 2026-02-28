from civil_engineering.cv_adapter.bullet_rewriter import rewrite_bullets

from civil_engineering.job_parser import ParsedJob

def main():
    bullets = [
        "Led site construction activities",
        "Assisted with preparation of site reports",
        "Responsible for supervising workers"
    ]

    profile = {
        "role": "Site Engineer",
        "experience": 11
    }

    job = ParsedJob(
        title="Civil Engineer",
        years_required=3,
        project_types=["Buildings", "Infrastructure"]
    )

    intelligence = {
        "seniority": "overqualified",
        "cv_tone": "focused, non-threatening, hands-on",
        "risk_flags": ["high_safety_environment"]
    }

    rewritten = rewrite_bullets(bullets, profile, job, intelligence)

    for b in rewritten:
        print(b)


if __name__ == "__main__":
    main()
