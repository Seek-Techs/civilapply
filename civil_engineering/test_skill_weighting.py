from civil_engineering.cv_adapter.skill_weighting import weight_skills
from civil_engineering.job_parser import ParsedJob

def main():
    profile = {
        "role": "Site Engineer",
        "experience": 11,
        "project_types": ["Buildings", "Industrial", "Refinery"]
    }

    job = ParsedJob(
        title="Civil Engineer",
        years_required=3,
        project_types=["Buildings", "Infrastructure"]
    )

    intelligence = {
        "seniority": "overqualified",
        "risk_flags": ["high_safety_environment"]
    }

    result = weight_skills(profile, job, intelligence)
    print(result)

if __name__ == "__main__":
    main()
