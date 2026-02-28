from civil_engineering.site_engineer_profile import get_site_engineer_profile
from civil_engineering.job_parser import parse_job_description
from civil_engineering.seniority import classify_seniority
from civil_engineering.cv_tone import determine_cv_tone
from civil_engineering.risk_flags import detect_risk_flags


def main():
    profile = get_site_engineer_profile()

    job_text = """
    Civil Engineer required with 3-5 years experience.
    Projects include buildings and infrastructure works.
    """

    job = parse_job_description(job_text)

    seniority = classify_seniority(profile, job)
    tone = determine_cv_tone(seniority)
    risks = detect_risk_flags(profile, job)

    print("Seniority:", seniority)
    print("CV Tone:", tone)
    print("Risk Flags:", risks)


if __name__ == "__main__":
    main()