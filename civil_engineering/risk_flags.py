# def detect_risk_flags(profile, job):
#     flags = []

#     if "Refinery" in profile["project_types"]:
#         flags.append("high_safety_environment")

#     if "Industrial" in job["project_types"]:
#         flags.append("permit_to_work")

#     return flags


def detect_risk_flags(profile, job):
    flags = []

    if "Refinery" in profile["project_types"]:
        flags.append("high_safety_environment")

    if "Industrial" in job.project_types:
        flags.append("permit_to_work")

    return flags
