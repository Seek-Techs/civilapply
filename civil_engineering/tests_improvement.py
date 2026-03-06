# civil_engineering/test_improvements.py
#
# ── HOW TO RUN ────────────────────────────────────────────────────────────────
# From the project root:
#   python -m pytest civil_engineering/test_improvements.py -v
# Or directly:
#   python civil_engineering/test_improvements.py
#
# ── WHAT WE'RE TESTING ───────────────────────────────────────────────────────
# Each test targets a specific bug that was fixed.
# Test names follow the pattern: test_<module>_<scenario>_<expected_result>
#
# ── SENIOR DEV APPROACH TO TESTS ─────────────────────────────────────────────
# Tests are the PROOF that your fix works.
# They are also the DOCUMENTATION of what the code is supposed to do.
# A test named "test_seniority_no_unbound_local_error" tells a future developer
# exactly what was broken and that it's now fixed.
#
# Structure: AAA
#   Arrange — set up inputs
#   Act     — call the function
#   Assert  — check the result is correct


import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import copy

# ── Shared test fixtures ───────────────────────────────────────────────────────
# These are the standard test objects reused across test classes.
# Keeping them in one place means: change the CV once, all tests update.

SAMPLE_CV = {
    "profile": {
        "name": "Sikiru Yusuff Olatunji",
        "title": "Civil Engineer",
        "experience_years": 11,
    },
    "experience": [
        {
            "role": "Project Monitoring Lead",
            "company": "IPMC",
            "bullets": [
                "- Verified contractor-executed concrete and structural works",
                "- Reviewed and certified contractor invoices",
                "- Ensured compliance with HSE and QA/QC standards",
            ],
        }
    ],
    "skills": ["site supervision", "quantity verification", "structural compliance", "Excel", "Power BI", "Python"],
    "project_types": ["infrastructure", "buildings"],
}

SAMPLE_JOB_INFRA = {
    "title": "Site Engineer",
    "years_required": 3,
    "project_types": ["Infrastructure"],
    "skills": ["site supervision", "QA/QC"],
}

SAMPLE_JOB_BUILDINGS = {
    "title": "Civil Engineer",
    "years_required": 12,
    "project_types": ["Buildings"],
}

SAMPLE_JOB_REFINERY = {
    "title": "Site Engineer",
    "years_required": 5,
    "project_types": ["refinery"],
}

SAMPLE_JOB_NO_YEARS = {
    "title": "Site Engineer",
    "project_types": ["Infrastructure"],
    # Note: no "years_required" key at all
}


passed = 0
failed = 0

def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        print(f"  ✓  {name}")
        passed += 1
    else:
        print(f"  ✗  FAIL: {name}")
        if detail:
            print(f"       → {detail}")
        failed += 1


# ════════════════════════════════════════════════════════════════════════════
# 1. TEST: intelligence/builder.py — UnboundLocalError fix
# ════════════════════════════════════════════════════════════════════════════
print("\n── Fix 1: intelligence/builder.py (UnboundLocalError) ──────────────────")

from civil_engineering.intelligence.builder_origin import build_intelligence, _classify_seniority

# Test the extracted _classify_seniority() function in isolation
check(
    "underqualified when years < required",
    _classify_seniority(experience_years=2, years_required=5, alignment_strength="none") == "underqualified"
)
check(
    "matched when gap <= 2",
    _classify_seniority(experience_years=5, years_required=5, alignment_strength="none") == "matched"
)
check(
    "matched when 1 year over",
    _classify_seniority(experience_years=6, years_required=5, alignment_strength="none") == "matched"
)
check(
    "tolerated_overqualified when gap > 2 and strong alignment",
    _classify_seniority(experience_years=11, years_required=3, alignment_strength="strong") == "tolerated_overqualified"
)
check(
    "overqualified when gap > 2 and no alignment",
    _classify_seniority(experience_years=11, years_required=3, alignment_strength="none") == "overqualified"
)
check(
    "unknown when years_required is None — no crash",
    _classify_seniority(experience_years=11, years_required=None, alignment_strength="none") == "unknown"
)

# Test build_intelligence() doesn't crash on None years_required
try:
    result = build_intelligence(SAMPLE_CV, SAMPLE_JOB_NO_YEARS)
    check("build_intelligence handles missing years_required", result["seniority"] == "unknown")
except Exception as e:
    check("build_intelligence handles missing years_required", False, str(e))

# Test normal case
result = build_intelligence(SAMPLE_CV, SAMPLE_JOB_INFRA)
check("strong alignment for matching project types", result["project_alignment"]["strength"] == "strong")
check("seniority is tolerated_overqualified (11 yrs vs 3)", result["seniority"] == "tolerated_overqualified")
check("risk_flags is empty for infrastructure job", "high_safety_environment" not in result["risk_flags"])

# Test refinery job triggers risk flag
result_refinery = build_intelligence(SAMPLE_CV, SAMPLE_JOB_REFINERY)
check("refinery job triggers high_safety_environment flag", "high_safety_environment" in result_refinery["risk_flags"])


# ════════════════════════════════════════════════════════════════════════════
# 2. TEST: pipeline mutation fix — deepcopy prevents cross-job contamination
# ════════════════════════════════════════════════════════════════════════════
print("\n── Fix 2: pipeline/run_application.py (CV mutation bug) ────────────────")

from civil_engineering.normalization.normalize_cv import normalize_cv

# Simulate what the old buggy code did
cv_original = copy.deepcopy(SAMPLE_CV)
cv_normalised = normalize_cv(cv_original)

# Run normalize_cv again on the ALREADY normalised CV (the bug)
skills_after_first  = len(cv_normalised.get("skills", []))
normalize_cv(cv_normalised)   # second call — simulates the bug
skills_after_second = len(cv_normalised.get("skills", []))

check(
    "normalize_cv is idempotent (same result if called twice)",
    skills_after_first == skills_after_second,
    f"First call: {skills_after_first} skills, second call: {skills_after_second} skills"
)

# Demonstrate that deepcopy prevents mutation
original_cv = {"skills": ["Excel"], "project_types": ["infrastructure"]}
normalised  = normalize_cv(copy.deepcopy(original_cv))
check("deepcopy protects original — original.skills unchanged", original_cv["skills"] == ["Excel"])
check("normalised copy can have more skills", len(normalised.get("skills", [])) >= 1)


# ════════════════════════════════════════════════════════════════════════════
# 3. TEST: bullet_rewriter.py — safety phrase no longer on every bullet
# ════════════════════════════════════════════════════════════════════════════
print("\n── Fix 3: cv_adapter/bullet_rewriter.py (unconditional safety phrase) ──")

from civil_engineering.cv_adapter.bullet_rewriter import rewrite_bullets, _is_site_activity

# Test the _is_site_activity guard directly
check("site supervision IS a site activity", _is_site_activity("Supervised concrete works on site"))
check("invoice review is NOT a site activity",  not _is_site_activity("Reviewed and certified contractor invoices"))
check("compliance IS a site activity", _is_site_activity("Ensured compliance with HSE standards"))
check("Excel reporting is NOT a site activity", not _is_site_activity("Produced Excel reports for cost tracking"))

# Test with infrastructure job (no risk flag → no safety phrase)
infra_intelligence = build_intelligence(SAMPLE_CV, SAMPLE_JOB_INFRA)
bullets_infra = rewrite_bullets(
    bullets=SAMPLE_CV["experience"][0]["bullets"],
    profile=SAMPLE_CV["profile"],
    job=SAMPLE_JOB_INFRA,
    intelligence=infra_intelligence,
)

# The invoice bullet should NOT have safety context for a non-risk job
invoice_bullet = [b for b in bullets_infra if "invoice" in b.lower()]
check("non-safety job: invoice bullet has no safety phrase",
      len(invoice_bullet) > 0 and "safety" not in invoice_bullet[0].lower())

# Test with refinery job (has risk flag → safety added to site bullets only)
refinery_intelligence = build_intelligence(SAMPLE_CV, SAMPLE_JOB_REFINERY)
bullets_refinery = rewrite_bullets(
    bullets=SAMPLE_CV["experience"][0]["bullets"],
    profile=SAMPLE_CV["profile"],
    job=SAMPLE_JOB_REFINERY,
    intelligence=refinery_intelligence,
)

concrete_bullet = [b for b in bullets_refinery if "concrete" in b.lower() or "structural" in b.lower() or "hse" in b.lower() or "compliance" in b.lower()]
invoice_bullet_r = [b for b in bullets_refinery if "invoice" in b.lower()]

check("refinery job: site activity bullet DOES get safety phrase",
      len(concrete_bullet) > 0 and any("safety" in b.lower() or "hse" in b.lower() for b in concrete_bullet))
check("refinery job: invoice bullet does NOT get safety phrase",
      len(invoice_bullet_r) > 0 and "safety" not in invoice_bullet_r[0].lower())

# All bullets should still start with "- "
check("all rewritten bullets start with '- '", all(b.startswith("- ") for b in bullets_infra))


# ════════════════════════════════════════════════════════════════════════════
# 4. TEST: guardrails/confidence_decay.py — KeyError fix
# ════════════════════════════════════════════════════════════════════════════
print("\n── Fix 4: guardrails/confidence_decay.py (KeyError bug) ────────────────")

from civil_engineering.guardrails.confidence_decay import apply_confidence_decay

# Old code: apply_confidence_decay(job_dict_without_confidence_key, [...])
# New code: apply_confidence_decay(base_confidence=70, job_title="Site Engineer", [...])

check("no previous applications → no decay", 
      apply_confidence_decay(70.0, "Site Engineer", []) == 70.0)

prev_apps_1 = [{"job_title": "Site Engineer"}]
check("1 previous application → -5 decay",
      apply_confidence_decay(70.0, "Site Engineer", prev_apps_1) == 65.0)

prev_apps_2 = [{"job_title": "Site Engineer"}, {"job_title": "Site Engineer"}]
check("2 previous applications → -12 decay",
      apply_confidence_decay(70.0, "Site Engineer", prev_apps_2) == 58.0)

prev_apps_3 = [{"job_title": "Site Engineer"}] * 3
check("3+ previous applications → hard block (0)",
      apply_confidence_decay(70.0, "Site Engineer", prev_apps_3) == 0.0)

check("different job title → no decay",
      apply_confidence_decay(70.0, "Civil Engineer", prev_apps_2) == 70.0)

check("no job title → no decay (safe default)",
      apply_confidence_decay(70.0, None, prev_apps_2) == 70.0)

check("score never goes below 0",
      apply_confidence_decay(5.0, "Site Engineer", prev_apps_1) == 0.0)


# ════════════════════════════════════════════════════════════════════════════
# 5. TEST: cover_letter_builder.py — personalised content
# ════════════════════════════════════════════════════════════════════════════
print("\n── Fix 5: cover_letter/cover_letter_builder.py (personalisation) ───────")

from civil_engineering.cover_letter.cover_letter_builder import build_cover_letter

intelligence_infra = build_intelligence(SAMPLE_CV, SAMPLE_JOB_INFRA)
letter_infra = build_cover_letter(
    profile=SAMPLE_CV["profile"],
    job=SAMPLE_JOB_INFRA,
    intelligence=intelligence_infra,
    cv=SAMPLE_CV,
)

check("cover letter contains job title", "Site Engineer" in letter_infra)
check("cover letter contains candidate name", "Sikiru" in letter_infra)
check("cover letter mentions skills", any(skill.lower() in letter_infra.lower() for skill in SAMPLE_CV["skills"][:3]))
check("cover letter has proper greeting", "Dear Hiring Manager" in letter_infra)
check("cover letter has closing", "sincerely" in letter_infra.lower())
check("cover letter is more than 4 lines", len(letter_infra.splitlines()) > 4)

# Test high-risk job gets safety paragraph
intelligence_refinery = build_intelligence(SAMPLE_CV, SAMPLE_JOB_REFINERY)
letter_refinery = build_cover_letter(
    profile=SAMPLE_CV["profile"],
    job=SAMPLE_JOB_REFINERY,
    intelligence=intelligence_refinery,
    cv=SAMPLE_CV,
)
check("high-risk job letter mentions HSE/safety", "hse" in letter_refinery.lower() or "safety" in letter_refinery.lower())

# Test normal job does NOT get safety paragraph
check("normal job letter doesn't include irrelevant safety paragraph",
      "hse" not in letter_infra.lower() or "safety" not in letter_infra.lower())


# ════════════════════════════════════════════════════════════════════════════
# 6. TEST: cv_tailor.py — stub replaced with functional fallback
# ════════════════════════════════════════════════════════════════════════════
print("\n── Fix 6: cv_tailor.py (stub → functional) ─────────────────────────────")

from civil_engineering.cv_tailor import generate_cv_summary, generate_cv_facts, ai_rewrite_cv

facts = generate_cv_facts(SAMPLE_CV, SAMPLE_JOB_INFRA)
check("generate_cv_facts extracts name", facts["name"] == "Sikiru Yusuff Olatunji")
check("generate_cv_facts finds project overlap", len(facts["overlap"]) > 0)
check("generate_cv_facts extracts job title", facts["job_title"] == "Site Engineer")

summary = generate_cv_summary(SAMPLE_CV, SAMPLE_JOB_INFRA)
check("rule-based summary is a non-empty string", isinstance(summary, str) and len(summary) > 20)
check("rule-based summary mentions experience years", "11" in summary)
check("rule-based summary mentions title", "Civil Engineer" in summary)

# Test no-API-key path returns a dict with all required keys (no crash, no stub)
result = ai_rewrite_cv(SAMPLE_CV, SAMPLE_JOB_INFRA, intelligence_infra, api_key="")
required_keys = {"summary", "key_skills_highlighted", "tailoring_rationale", "ats_keywords_used"}
check("no-API-key path returns dict with all required keys", required_keys.issubset(result.keys()))
check("no-API-key summary is a real string", isinstance(result["summary"], str) and len(result["summary"]) > 20)
check("no-API-key rationale explains fallback", "fallback" in result["tailoring_rationale"].lower())


# ════════════════════════════════════════════════════════════════════════════
# RESULTS
# ════════════════════════════════════════════════════════════════════════════
print(f"\n{'═' * 60}")
print(f"  {passed} passed   {failed} failed   ({passed + failed} total)")
print(f"{'═' * 60}")
if failed == 0:
    print("  ✅ All fixes verified.")
else:
    print("  ❌ Some tests failed — check output above.")