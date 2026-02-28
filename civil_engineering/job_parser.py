# import re

# def parse_job_description(text):
#     job = {
#         "title": None,
#         "years_required": None,
#         "project_types": [],
#     }

#     text_lower = text.lower()

#     # -------------------------
#     # ROLE / TITLE EXTRACTION
#     # -------------------------
#     ROLE_KEYWORDS = {
#         "Site Engineer": ["site engineer"],
#         "Civil Engineer": ["civil engineer"],
#         "Structural Engineer": ["structural engineer"],
#         "Civil / Structural Engineer": [
#             "civil / structural engineer",
#             "civil structural engineer"
#         ],
#     }

#     for role, patterns in ROLE_KEYWORDS.items():
#         for pattern in patterns:
#             if pattern in text_lower:
#                 job["title"] = role
#                 break
#         if job["title"]:
#             break

#     # -------------------------
#     # YEARS OF EXPERIENCE
#     # -------------------------
#     years_match = re.search(r"(\d+)\s*[-–to]+\s*(\d+)?\s*years", text_lower)
#     if years_match:
#         # take the upper bound if range exists (e.g. 3–5 years → 5)
#         job["years_required"] = int(years_match.group(2) or years_match.group(1))
#     else:
#         years_match = re.search(r"(\d+)\+?\s+years", text_lower)
#         if years_match:
#             job["years_required"] = int(years_match.group(1))

#     # -------------------------
#     # PROJECT TYPE EXTRACTION
#     # -------------------------
#     PROJECT_KEYWORDS = {
#         "Buildings": ["building"],
#         "Infrastructure": ["infrastructure", "road", "bridge", "drainage"],
#         "Industrial": ["industrial", "plant", "factory", "refinery"],
#         "Water & Sewage": ["sewage", "treatment plant", "water"],
#     }

#     for project, keywords in PROJECT_KEYWORDS.items():
#         for kw in keywords:
#             if kw in text_lower:
#                 job["project_types"].append(project)
#                 break

#     return job

import re
from civil_engineering.domain.job import ParsedJob


PROJECT_KEYWORDS = {
    "Buildings": ["building"],
    "Infrastructure": ["infrastructure", "road", "bridge", "drainage"],
    "Industrial": ["industrial", "plant", "factory", "refinery"],
    "Water & Sewage": ["sewage", "treatment plant", "water"],
}


def parse_job_description(text):
    job = ParsedJob()

    # Job title
    if re.search(r"civil\s*/?\s*structural\s+engineer", text, re.IGNORECASE):
        job.title = "Civil Engineer"

    # Years of experience
    years_match = re.search(r"(\d+)\s*[–-]?\s*(\d+)?\s*years", text, re.IGNORECASE)
    if years_match:
        job.years_required = int(years_match.group(1))

    # Project types
    text_lower = text.lower()
    for project, keywords in PROJECT_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                job.project_types.append(project)
                break

    return job
