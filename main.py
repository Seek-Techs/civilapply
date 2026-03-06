#!/usr/bin/env python3
# main.py
#
# ENTRY POINT — where the program starts.
# 
# SENIOR DEV: main.py should be THIN.
# It loads config, builds objects, and calls the pipeline.
# All real logic lives in other modules.
#
# Think of main.py as a "wiring diagram" — it connects parts together.

import logging
import sys
import json
from pathlib import Path

from config import AppConfig
from models import CandidateProfile, WorkExperience, JobPosting, ProjectType
from job_parser import parse_job_description
from pipeline.runner import process_all_jobs


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the whole application."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def load_profile_from_json(path: str) -> CandidateProfile:
    """
    Load a candidate profile from a JSON file.
    
    SENIOR DEV: Data loading code lives in its own function,
    not tangled with business logic. Easy to swap for a DB query later.
    """
    with open(path) as f:
        data = json.load(f)

    profile_data = data.get("profile", {})
    experience_data = data.get("experience", [])
    skills = data.get("skills", [])

    work_history = [
        WorkExperience(
            role=exp.get("role", ""),
            company=exp.get("company", ""),
            years=exp.get("years", 0),
            bullets=exp.get("bullets", []),
        )
        for exp in experience_data
    ]

    return CandidateProfile(
        name=profile_data.get("name", "Unknown"),
        title=profile_data.get("title", "Civil Engineer"),
        total_years=profile_data.get("experience_years", 0),
        work_history=work_history,
        technical_skills=skills,
        project_types=["Infrastructure", "Buildings", "Industrial"],  # inferred from CV
        desired_roles=["Civil Engineer", "Site Engineer", "Structural Engineer"],
    )


def load_jobs_from_directory(jobs_dir: str) -> list[JobPosting]:
    """Load all job postings from a directory of JSON files."""
    jobs = []
    jobs_path = Path(jobs_dir)

    if not jobs_path.exists():
        logging.warning("Jobs directory not found: %s", jobs_dir)
        return jobs

    for job_file in sorted(jobs_path.glob("*.json")):
        with open(job_file) as f:
            data = json.load(f)

        project_types = [
            ProjectType(pt) for pt in data.get("project_types", [])
            if pt in ProjectType._value2member_map_
        ]

        job = JobPosting(
            job_id=job_file.stem,
            title=data.get("title"),
            years_required=data.get("years_required"),
            project_types=project_types,
        )
        jobs.append(job)
        logging.debug("Loaded job: %s", job.job_id)

    logging.info("Loaded %d jobs from %s", len(jobs), jobs_dir)
    return jobs


def demo_run() -> None:
    """
    Demo run with hardcoded data — no files needed.
    Good for learning and quick testing.
    """
    profile = CandidateProfile(
        name="Sikiru Olatunji",
        title="Civil Engineer",
        total_years=11,
        technical_skills=["AutoCAD", "Python", "Excel", "Power BI", "Prota Software"],
        project_types=["Infrastructure", "Buildings", "Industrial"],
        desired_roles=["Civil Engineer", "Site Engineer"],
    )

    # Parse real job descriptions (as text)
    job_texts = [
        """Site Engineer — London, UK
        We are seeking an experienced Site Engineer for infrastructure and road projects.
        Requirements: 3+ years of site experience. Salary: £40,000 - £50,000.
        Skills: AutoCAD, site supervision, QA/QC.""",

        """Civil Engineer — Manchester
        Senior Civil/Structural Engineer required for a major buildings project.
        10-15 years experience in commercial construction. £65,000 - £80,000.
        Strong knowledge of structural analysis software required.""",

        """Graduate Site Engineer — Birmingham
        Entry level position for a water treatment project. 0-2 years experience.
        Training provided. £28,000.""",
    ]

    jobs = [
        parse_job_description(text, job_id=f"demo_{i+1:03d}")
        for i, text in enumerate(job_texts)
    ]

    config = AppConfig()
    decisions = process_all_jobs(profile, jobs, config, save_output=False)

    # Print results
    print("\n" + "="*60)
    print(f"  RESULTS FOR {profile.name.upper()}")
    print("="*60)

    for decision in decisions:
        match = decision.match_result
        status = "✓ APPLY" if decision.should_apply else "✗ SKIP"
        score = f"{match.total_score:.1f}/100" if match else "N/A"

        print(f"\n[{status}] Job: {decision.job_id}")
        print(f"  Score:  {score}")
        print(f"  Reason: {decision.reason}")
        if decision.cv_summary:
            print(f"  CV Summary: {decision.cv_summary[:100]}...")


if __name__ == "__main__":
    setup_logging("INFO")
    demo_run()