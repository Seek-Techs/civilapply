# from job_matcher import match_site_engineer
from civil_engineering.job_matcher import match_site_engineer


profile = {
    "role": "Site Engineer",
    "experience": 11,
    "project_types": [
        "Buildings",
        "Sewage Treatment Plant",
        "Industrial",
        "Refinery"
    ]
}

job = {
    "title": "Site Engineer",
    "years_required": 8,
    "project_types": [
        "Buildings",
        "Industrial",
        "Infrastructure"
    ]
}

result = match_site_engineer(profile, job)

print("Match Result:")
print(result)
