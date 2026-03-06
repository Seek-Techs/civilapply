import os

ROOT = os.path.dirname(os.path.abspath(__file__))

def check(label, path, signatures):
    full = os.path.join(ROOT, path)
    print(f"\n{'─'*50}")
    print(f"  {label}")
    print(f"  {full}")
    if not os.path.exists(full):
        print("  ✗ FILE NOT FOUND")
        return
    with open(full, encoding='utf-8', errors='replace') as f:
        content = f.read()
    all_ok = True
    for sig, desc in signatures:
        found = sig in content
        mark  = "✓" if found else "✗ NEEDS REPLACING"
        if not found:
            all_ok = False
        print(f"  {mark}  {desc}")
    if all_ok:
        print("  ✅ UP TO DATE")
    else:
        print("  ❌ THIS FILE IS OLD — replace it")

check("job_parser.py", "civil_engineering/job_parser.py", [
    ("requirement_patterns", "has smart years extraction"),
    ("job_section", "skips company intro for project types"),
    ("naira_match", "detects Nigerian salary"),
    ("cage fabrication", "detects rebar/construction keywords"),
])

check("cv.json", "civil_engineering/data/cv.json", [
    ("Independent Project Monitoring", "has real job history"),
    ("reinforcement inspection", "has detailed bullets"),
    ("ProtaStructure", "has real skills"),
    ("Nego Construction", "has second job role"),
])

check("job_filter.py", "civil_engineering/eligibility/job_filter.py", [
    ("event production", "uses multi-word non-engineering phrases"),
    ("not eng_hits", "rejects events-only jobs correctly"),
])

check("cv_tailor.py", "civil_engineering/cv_tailor.py", [
    ("_call_cohere", "has Cohere support"),
    ("_call_ollama", "has Ollama support"),
])

check("apply.py", "apply.py", [
    ("_load_env_file", "loads .env automatically"),
    ("ai_summary", "passes AI summary to cover letter"),
])

check(".env", ".env", [
    ("COHERE_API_KEY", "has Cohere key"),
])

print(f"\n{'='*50}")
print("  Replace every file marked ❌ above")
print(f"{'='*50}\n")
