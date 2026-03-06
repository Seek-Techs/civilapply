# config/settings.py
#
# SENIOR DEV RULE: All "magic numbers" live in config, never in logic.
#
# BAD (scattered in code):
#   if score >= 80:   # what is 80? why 80? can we change it?
#
# GOOD (centralised here):
#   if score >= config.matching.auto_apply_threshold
#
# Now the number has a name, is documented, and can be changed in one place.

from dataclasses import dataclass, field
import os


@dataclass
class MatchingConfig:
    """Controls how the matching algorithm scores jobs. Weights must sum to 100."""
    weight_role_match: int = 30
    weight_experience: int = 30
    weight_projects: int = 40

    auto_apply_threshold: float = 75.0
    review_threshold: float = 55.0

    def __post_init__(self):
        # __post_init__ runs after __init__ on dataclasses.
        # Use it to validate relationships between fields.
        total = self.weight_role_match + self.weight_experience + self.weight_projects
        if total != 100:
            raise ValueError(f"Weights must sum to 100, got {total}")


@dataclass
class GuardrailConfig:
    """Limits that prevent over-applying. Protects the candidate's reputation."""
    max_applications_per_day: int = 10
    max_applications_per_week: int = 40
    max_applications_per_company: int = 2
    cooldown_hours_after_rejection: int = 72


@dataclass
class AppConfig:
    """
    Root config object. One instance flows through the entire app.

    SENIOR DEV PATTERN: "Config root object"
    Instead of 10 different config dicts floating around, there is ONE
    AppConfig. Every module receives it. You always know where config lives.
    """
    matching: MatchingConfig = field(default_factory=MatchingConfig)
    guardrails: GuardrailConfig = field(default_factory=GuardrailConfig)

    # API keys ALWAYS come from environment variables — NEVER hardcoded.
    # If you hardcode a key and commit it to Git, it leaks permanently.
    anthropic_api_key: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "")
    )

    # Two models: fast/cheap for filtering, quality for CV tailoring
    llm_model_fast: str = "claude-haiku-4-5-20251001"
    llm_model_quality: str = "claude-sonnet-4-6"

    output_dir: str = "output"
    log_level: str = "INFO"

    def __post_init__(self):
        if not self.anthropic_api_key:
            import warnings
            warnings.warn(
                "ANTHROPIC_API_KEY not set. "
                "Run: export ANTHROPIC_API_KEY=your_key_here",
                stacklevel=2
            )

    @classmethod
    def from_env(cls) -> "AppConfig":
        """
        Factory method: build config from environment variables.

        SENIOR DEV PATTERN: factory methods are named from_X().
        They let you create objects from different sources without
        overloading __init__ with conditional logic.

        Usage:
            config = AppConfig.from_env()   # production
            config = AppConfig()            # tests (safe defaults)
        """
        return cls(
            matching=MatchingConfig(
                auto_apply_threshold=float(
                    os.getenv("AUTO_APPLY_THRESHOLD", "75")
                ),
            ),
            guardrails=GuardrailConfig(
                max_applications_per_day=int(
                    os.getenv("MAX_APPS_PER_DAY", "10")
                ),
            ),
        )