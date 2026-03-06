# tests/test_core.py
#
# HOW SENIOR DEVS WRITE TESTS
#
# Tests are not an afterthought — they ARE the specification.
# Before writing logic, a senior dev writes the test that says:
# "given THIS input, I expect THAT output".
#
# NAMING CONVENTION:
# test_<what>_<condition>_<expected>()
# e.g. test_experience_score_shortfall_returns_partial_credit
#
# STRUCTURE: AAA pattern (every test has three sections)
# Arrange — set up the data
# Act     — call the function
# Assert  — check the result
#
# WHY NOT JUST RUN THE CODE AND SEE?
# Because tests run in 0.01 seconds. Running the full app takes minutes.
# Tests catch regressions: changes that break old behaviour.
# Without tests, refactoring is dangerous. With tests, it's safe.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from models import CandidateProfile, JobPosting, ProjectType, SeniorityLevel
from job_parser import parse_job_description
from matcher.engine import (
    match_candidate_to_job,
    _score_role, _score_experience, _score_projects, _classify_seniority
)
from config import AppConfig, MatchingConfig


# ── Fixtures ──────────────────────────────────────────────────────────────────
# SENIOR DEV: Fixtures are shared test data.
# @pytest.fixture creates reusable objects for multiple tests.
# This avoids copy-pasting the same setup in every test function.

@pytest.fixture
def config():
    """Standard app config for tests. Uses safe defaults."""
    return AppConfig()


@pytest.fixture
def civil_engineer():
    """A sample civil engineer with 11 years of experience."""
    return CandidateProfile(
        name="Sikiru Olatunji",
        title="Civil Engineer",
        total_years=11,
        project_types=["Infrastructure", "Buildings", "Industrial"],
        technical_skills=["AutoCAD", "Python", "Excel", "Power BI", "Prota Software"],
        desired_roles=["Civil Engineer", "Site Engineer", "Structural Engineer"],
    )


@pytest.fixture
def site_engineer_job():
    """A sample site engineer job posting."""
    return JobPosting(
        job_id="job_001",
        title="Site Engineer",
        years_required=3,
        project_types=[ProjectType.INFRASTRUCTURE],
    )


# ── Parser tests ──────────────────────────────────────────────────────────────

class TestJobParser:
    """Tests for the job description parser."""

    def test_parse_extracts_title(self):
        # Arrange
        text = "We are looking for an experienced Site Engineer to join our team."
        # Act
        job = parse_job_description(text, job_id="test_001")
        # Assert
        assert job.title == "Site Engineer"

    def test_parse_extracts_years_single(self):
        text = "Minimum 5 years of relevant experience required."
        job = parse_job_description(text, job_id="test_002")
        assert job.years_required == 5

    def test_parse_extracts_years_range(self):
        # Range "3-7 years" should return the lower bound (3)
        text = "The successful candidate will have 3-7 years of site experience."
        job = parse_job_description(text)
        assert job.years_required == 3

    def test_parse_extracts_project_types(self):
        text = "Experience on road and bridge infrastructure projects required."
        job = parse_job_description(text)
        assert ProjectType.INFRASTRUCTURE in job.project_types

    def test_parse_extracts_salary(self):
        text = "Salary: £35,000 - £45,000 depending on experience."
        job = parse_job_description(text)
        assert job.salary_min == 35000
        assert job.salary_max == 45000

    def test_parse_empty_text_raises(self):
        # SENIOR DEV: Test that errors are raised correctly, not just success cases
        with pytest.raises(ValueError):
            parse_job_description("")

    def test_parse_unknown_title_returns_none(self):
        text = "We need a plumber with 5 years experience."
        job = parse_job_description(text)
        assert job.title is None


# ── Matcher tests ─────────────────────────────────────────────────────────────

class TestMatcher:
    """Tests for the matching engine."""

    def test_full_match_returns_high_score(self, civil_engineer, site_engineer_job, config):
        # Arrange — profile perfectly matches the job
        # Act
        result = match_candidate_to_job(civil_engineer, site_engineer_job, config)
        # Assert — with 11 years vs 3 required and matching projects, should score high
        assert result.total_score >= 75.0
        assert result.qualified is True

    def test_no_project_overlap_reduces_score(self, civil_engineer, config):
        # Arrange — job requires Energy projects, candidate has none
        job = JobPosting(
            job_id="energy_job",
            title="Site Engineer",
            years_required=3,
            project_types=[ProjectType.ENERGY],
        )
        # Act
        result = match_candidate_to_job(civil_engineer, job, config)
        # Assert — project score should be 0
        assert result.score_projects == 0.0

    def test_insufficient_experience_partial_score(self, config):
        # Arrange — junior candidate (2 years) vs senior job (10 years)
        junior = CandidateProfile(
            name="Junior Dev",
            title="Graduate Civil Engineer",
            total_years=2,
            project_types=["Infrastructure"],
            desired_roles=["Civil Engineer"],
        )
        job = JobPosting(
            job_id="senior_job",
            title="Civil Engineer",
            years_required=10,
        )
        # Act
        result = match_candidate_to_job(junior, job, config)
        # Assert — experience score should be partial, not zero
        assert 0 < result.score_experience < config.matching.weight_experience

    def test_seniority_overqualified(self, civil_engineer, config):
        # civil_engineer has 11 years, job needs 3 → gap of 8 → overqualified
        job = JobPosting(job_id="j", title="Site Engineer", years_required=3)
        result = match_candidate_to_job(civil_engineer, job, config)
        assert result.seniority == SeniorityLevel.OVERQUALIFIED

    def test_seniority_mid_when_meets_exactly(self, config):
        profile = CandidateProfile(
            name="Test", title="Civil Engineer", total_years=5,
            desired_roles=["Civil Engineer"]
        )
        job = JobPosting(job_id="j", title="Civil Engineer", years_required=5)
        result = match_candidate_to_job(profile, job, config)
        assert result.seniority == SeniorityLevel.MID

    def test_result_has_reasons(self, civil_engineer, site_engineer_job, config):
        result = match_candidate_to_job(civil_engineer, site_engineer_job, config)
        # Each dimension should produce a reason string
        assert len(result.reasons) == 3
        assert all(isinstance(r, str) for r in result.reasons)

    def test_result_has_top_strength_and_gap(self, civil_engineer, site_engineer_job, config):
        result = match_candidate_to_job(civil_engineer, site_engineer_job, config)
        assert result.top_strength is not None
        assert result.top_gap is not None


# ── Config tests ──────────────────────────────────────────────────────────────

class TestConfig:
    """Tests for configuration validation."""

    def test_weights_must_sum_to_100(self):
        # This should raise because 30+30+30 = 90, not 100
        with pytest.raises(ValueError, match="sum to 100"):
            MatchingConfig(
                weight_role_match=30,
                weight_experience=30,
                weight_projects=30,  # total = 90
            )

    def test_valid_config_creates_successfully(self):
        config = AppConfig()
        assert config.matching.weight_role_match + \
               config.matching.weight_experience + \
               config.matching.weight_projects == 100


# ── Model tests ───────────────────────────────────────────────────────────────

class TestModels:
    """Tests for model helper methods."""

    def test_has_skill_case_insensitive(self, civil_engineer):
        assert civil_engineer.has_skill("autocad") is True
        assert civil_engineer.has_skill("AUTOCAD") is True
        assert civil_engineer.has_skill("AutoCAD") is True

    def test_has_skill_missing(self, civil_engineer):
        assert civil_engineer.has_skill("Revit") is False

    def test_project_overlap_partial(self, civil_engineer):
        overlap = civil_engineer.project_overlap(["Infrastructure", "Energy"])
        assert "Infrastructure" in overlap
        assert "Energy" not in overlap

    def test_salary_display_range(self):
        job = JobPosting(job_id="j", salary_min=40000, salary_max=55000)
        assert "40,000" in job.salary_display()
        assert "55,000" in job.salary_display()

    def test_salary_display_not_specified(self):
        job = JobPosting(job_id="j")
        assert job.salary_display() == "Not specified"