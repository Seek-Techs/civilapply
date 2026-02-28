# civil_engineering/platforms/platform_selector.py

from civil_engineering.platforms.platform_rules import PLATFORM_RULES


def select_platform(job):
    """
    Determines best application platform for a job.
    """

    source = job.get("source", "").lower()

    if "linkedin" in source:
        return "linkedin"
    elif "email" in source:
        return "email"
    elif "ats" in source:
        return "ats"

    # Default fallback
    return "email"


def get_platform_policy(platform):
    return PLATFORM_RULES.get(platform)
