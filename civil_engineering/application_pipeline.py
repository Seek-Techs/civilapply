from civil_engineering.site_engineer_profile import get_site_engineer_profile
from civil_engineering.matcher_service import match_profile_to_job
from civil_engineering.cv_tailor import generate_cv_summary


def process_job_application(job):
    profile = get_site_engineer_profile()

    match_result = match_profile_to_job(profile, job)

    if not match_result["qualified"]:
        return {
            "apply": False,
            "reason": "Profile does not meet job requirements"
        }

    cv_summary = generate_cv_summary(profile, job)

    return {
        "apply": True,
        "score": match_result["score"],
        "cv_summary": cv_summary
    }
