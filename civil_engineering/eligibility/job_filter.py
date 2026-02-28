# civil_engineering/eligibility/job_filter.py

ENGINEERING_KEYWORDS = [
    "civil",
    "site",
    "construction",
    "structural",
    "infrastructure",
    "project",
    "field",
    "works",
    "qa",
    "qc"
]

PROJECT_KEYWORDS = [
    "building",
    "infrastructure",
    "industrial",
    "refinery",
    "road",
    "bridge",
    "drainage",
    "sewage",
    "water"
]


def is_job_relevant(cv, job):
    cv_domain = set(p.lower() for p in cv.get("project_types", []))
    job_domain = set(p.lower() for p in job.get("project_types", []))

    overlap = cv_domain & job_domain

    if overlap:
        return True, "Direct project-type overlap"

    transferable_domains = {"infrastructure", "construction", "engineering"}

    if job_domain & transferable_domains:
        return True, "Transferable engineering domain"

    return False, "Job is outside core civil engineering expertise"
