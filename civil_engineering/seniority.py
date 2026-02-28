def classify_seniority(profile, job):
    years = profile["experience"]
    required = job.years_required

    if required is None:
        return "unknown"

    if years >= required + 5:
        return "overqualified"
    elif years >= required + 2:
        return "senior"
    elif years >= required:
        return "mid"
    else:
        return "junior"
