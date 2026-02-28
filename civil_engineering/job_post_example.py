SITE_ENGINEER_JOB = {
    "job_title": "Site Engineer",
    "company": "ABC Construction Ltd",
    "location": "Lagos, Nigeria",
    "years_required": 8,

    "project_type": [
        "Buildings",
        "Industrial",
        "Infrastructure"
    ],

    "key_responsibilities": [
        "Supervise site activities",
        "Ensure compliance with drawings and specifications",
        "Coordinate subcontractors",
        "Quality control and inspections",
        "Health and safety enforcement"
    ],

    "required_skills": [
        "Site supervision",
        "Concrete works",
        "Reinforcement detailing",
        "Construction scheduling",
        "Health and safety"
    ]
}


if __name__ == "__main__":
    print("Job Title:", SITE_ENGINEER_JOB["job_title"])
    print("Company:", SITE_ENGINEER_JOB["company"])
    print("Years Required:", SITE_ENGINEER_JOB["years_required"])
    print("Project Types:", ", ".join(SITE_ENGINEER_JOB["project_type"]))
