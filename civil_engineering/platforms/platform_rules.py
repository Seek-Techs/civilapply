# civil_engineering/platforms/platform_rules.py

PLATFORM_RULES = {
    "linkedin": {
        "daily_limit": 3,
        "confidence_threshold": 70,
        "cv_variant": "targeted",
        "auto_apply_allowed": True
    },
    "email": {
        "daily_limit": 5,
        "confidence_threshold": 60,
        "cv_variant": "narrative",
        "auto_apply_allowed": False
    },
    "ats": {
        "daily_limit": 4,
        "confidence_threshold": 65,
        "cv_variant": "structured",
        "auto_apply_allowed": True
    }
}
