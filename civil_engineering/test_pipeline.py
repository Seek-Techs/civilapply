from civil_engineering.application_pipeline import process_job_application


job = {
    "title": "Site Engineer",
    "years_required": 8,
    "project_types": [
        "Buildings",
        "Industrial",
        "Infrastructure"
    ]
}

result = process_job_application(job)

print("Application Decision:")
print(result)
