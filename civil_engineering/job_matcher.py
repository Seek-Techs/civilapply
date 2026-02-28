# # civil_engineering/job_matcher.py

# def match_site_engineer(profile, job):
#     score = 0
#     reasons = []

#     # 1. Experience check (40%)
#     if profile["experience"] >= job["years_required"]:
#         score += 40
#         reasons.append("Experience requirement met")
#     else:
#         reasons.append("Insufficient experience")

#     # 2. Project type overlap (40%)
#     profile_projects = set(profile["project_types"])
#     job_projects = set(job["project_types"])

#     overlap = profile_projects.intersection(job_projects)

#     if overlap:
#         project_score = (len(overlap) / len(job_projects)) * 40
#         score += project_score
#         reasons.append(f"Project match: {', '.join(overlap)}")
#     else:
#         reasons.append("No matching project experience")

#     # 3. Role match (20%)
#     if profile["role"].lower() in job["title"].lower():
#         score += 20
#         reasons.append("Role title matches")

#     qualified = score >= 70

#     return {
#         "score": round(score, 1),
#         "qualified": qualified,
#         "reasons": reasons
#     }

def match_site_engineer(profile, job):
    score = 0
    reasons = []

    # --- Role Match (30%)
    if job["title"] and profile["role"].lower() in job["title"].lower():
        score += 30
        reasons.append("Role title matches")

    # --- Experience Match (30%)
    if job["years_required"] is not None:
        if profile["experience"] >= job["years_required"]:
            score += 30
            reasons.append("Experience requirement met")
        else:
            reasons.append("Insufficient experience")

    # --- Project Type Match (40%)
    job_projects = set(job["project_types"])
    profile_projects = set(profile["project_types"])

    overlap = job_projects & profile_projects

    if overlap:
        project_score = (len(overlap) / len(job_projects)) * 40
        score += project_score
        reasons.append(f"Project match: {', '.join(overlap)}")

    qualified = score >= 70

    return {
        "score": round(score, 1),
        "qualified": qualified,
        "reasons": reasons
    }

