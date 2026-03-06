# apply.py  —  Run from project root: python apply.py

import sys, os, copy, json

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load_env_file():
    """
    Load a .env file from the project root into os.environ.

    WHY THIS FUNCTION EXISTS:
    Python does not automatically read .env files.
    A .env file is just a text file with KEY=VALUE lines.
    This function reads it manually and sets each variable in os.environ,
    so the rest of the code can use os.environ.get("GROQ_API_KEY") normally.

    WHY NOT USE python-dotenv LIBRARY?
    python-dotenv is a popular package that does the same thing,
    but it requires installation (pip install python-dotenv).
    This function does the same job with zero dependencies — just Python.

    .env file format expected:
        GROQ_API_KEY=gsk_abc123...
        ANTHROPIC_API_KEY=sk-ant-...

    Lines starting with # are comments and are ignored.
    """
    env_path = os.path.join(ROOT, ".env")

    if not os.path.exists(env_path):
        return   # no .env file — that's fine, use system env vars

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Skip blank lines and comments
            if not line or line.startswith("#"):
                continue

            # Skip lines without an = sign
            if "=" not in line:
                continue

            # Split on the FIRST = only
            # This handles values that contain = signs (e.g. base64 tokens)
            key, value = line.split("=", 1)
            key   = key.strip()
            value = value.strip()

            # Remove surrounding quotes if present
            # Some .env files write: GROQ_API_KEY="gsk_abc..."
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]

            # Only set if not already in environment
            # System environment variables take priority over .env
            if key and value and key not in os.environ:
                os.environ[key] = value


# Load .env FIRST — before any other imports that might use env vars
_load_env_file()


from civil_engineering.job_parser                        import parse_job_description
from civil_engineering.normalization.normalize_cv        import normalize_cv
from civil_engineering.intelligence.builder              import build_intelligence
from civil_engineering.cv_adapter.adapter                import adapt_cv
from civil_engineering.cover_letter.cover_letter_builder import build_cover_letter
from civil_engineering.cv_tailor                         import ai_rewrite_cv, generate_cv_summary
from civil_engineering.cv_pdf                            import generate_cv_pdf
from civil_engineering.scoring.job_ranker                import rank_job
from civil_engineering.decision_explainer                import explain_decisions
from civil_engineering.eligibility.job_filter            import is_job_relevant

CV_PATH = os.path.join(ROOT, "civil_engineering", "data", "cv.json")


def _load_cv() -> dict:
    with open(CV_PATH, "r", encoding="utf-8") as f:
        raw_cv = json.load(f)
    return normalize_cv(raw_cv)


# ── Display helpers ───────────────────────────────────────────────────────────

def _div(char="─", w=60): return char * w
def _header(t):  return f"\n{_div('═')}\n  {t}\n{_div('═')}"
def _section(t): return f"\n{_div()}\n  {t}\n{_div()}"

def _print_job_summary(job) -> None:
    print(_section("📋  JOB PARSED"))
    print(f"  Title          : {job.title or 'Not detected'}")
    print(f"  Years required : {job.years_required or 'Not specified'}")
    print(f"  Project types  : {', '.join(job.project_types) or 'Not detected'}")
    print(f"  Salary         : {job.salary or 'Not specified'}")
    print(f"  Location       : {job.location or 'Not specified'}")
    if job.required_skills:
        print(f"  Skills wanted  : {', '.join(job.required_skills[:5])}")
    if job.apply_email:
        print(f"  Apply to       : {job.apply_email}  ← send your CV here")

def _print_not_relevant(reason: str) -> None:
    print(_section("⛔  NOT A CIVIL ENGINEERING ROLE — SKIPPED"))
    print()
    words, line = reason.split(), "  "
    for w in words:
        if len(line) + len(w) + 1 > 70:
            print(line); line = "  " + w + " "
        else:
            line += w + " "
    if line.strip(): print(line)
    print()
    print("  Paste a civil / structural / infrastructure engineering")
    print("  role for this tool to generate a relevant application.")

def _print_decision(confidence: int, ranking: dict, intelligence: dict) -> None:
    print(_section("🎯  MATCH ANALYSIS"))
    seniority  = intelligence.get("seniority", "unknown")
    alignment  = intelligence.get("project_alignment", {}).get("strength", "none")
    risk_flags = intelligence.get("risk_flags", [])

    filled = int(confidence / 5)
    bar    = "█" * filled + "░" * (20 - filled)
    print(f"  Confidence     : [{bar}] {confidence}/100")
    print(f"  Seniority fit  : {seniority.replace('_', ' ').title()}")
    print(f"  Project match  : {alignment.title()}")
    if risk_flags:
        print(f"  Risk flags     : ⚠  {', '.join(f.replace('_',' ') for f in risk_flags)}")
    print()

    if ranking["rank"] == "strong_fit":
        print(f"  ✅  RECOMMENDATION: APPLY CONFIDENTLY")
    elif ranking["rank"] == "strategic_fit":
        print(f"  ⚠️   RECOMMENDATION: APPLY — but manage expectations")
    else:
        print(f"  ❌  RECOMMENDATION: DO NOT APPLY")
        print(f"      Confidence too low. This role is outside your strong match range.")

def _print_cv_summary(summary: str, provider: str) -> None:
    print(_section(f"📄  TAILORED CV SUMMARY  [{provider.upper()}]"))
    print()
    words, line = summary.split(), "  "
    for w in words:
        if len(line) + len(w) + 1 > 72:
            print(line); line = "  " + w + " "
        else:
            line += w + " "
    if line.strip(): print(line)
    print()
    print("  ↑ Paste this into the Profile/Summary section of your CV.")

def _print_cover_letter(letter: str) -> None:
    print(_section("✉️   COVER LETTER"))
    print()
    for line in letter.split("\n"):
        print(f"  {line}")
    print()
    print("  ↑ Paste this into your email or application form.")


# ── Input ─────────────────────────────────────────────────────────────────────

def _get_job_description() -> str:
    print(f"\n{_div()}")
    print("  Paste the job description below.")
    print("  Press Enter TWICE (blank line) when finished.")
    print(f"{_div()}\n")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "" and lines and lines[-1] == "":
            break
        lines.append(line)
    return "\n".join(lines).strip()


# ── Core pipeline ─────────────────────────────────────────────────────────────

def process_job_description(raw_text: str, base_cv: dict) -> None:

    # Step 1: Parse
    job      = parse_job_description(raw_text)
    job_dict = job.to_dict()
    _print_job_summary(job)

    # Step 2: Relevance check — pass raw_text for full content scanning
    is_relevant, reason = is_job_relevant(base_cv, job_dict, raw_text=raw_text)
    if not is_relevant:
        _print_not_relevant(reason)
        return

    # Step 3: Intelligence
    cv           = copy.deepcopy(base_cv)
    intelligence = build_intelligence(cv, job_dict)

    # Step 4: Score
    decisions        = explain_decisions(cv, job_dict, intelligence)
    confidence_block = next((d for d in decisions if d.get("type") == "confidence_score"), None)
    confidence       = confidence_block["overall_confidence"] if confidence_block else 0
    ranking          = rank_job(confidence)
    _print_decision(confidence, ranking, intelligence)

    # Step 5: Adapt CV bullets
    adapted_cv = adapt_cv(cv, job_dict, intelligence)

    # Step 6: AI CV summary
    tailor_result = ai_rewrite_cv(adapted_cv, job_dict, intelligence)
    cv_summary    = tailor_result.get("summary") or generate_cv_summary(adapted_cv, job_dict)
    provider      = tailor_result.get("provider", "rule-based")
    _print_cv_summary(cv_summary, provider)

    # Step 7: Cover letter
    cover_letter = build_cover_letter(
        profile      = cv.get("profile", {}),
        job          = job_dict,
        intelligence = intelligence,
        cv           = adapted_cv,
        ai_summary   = cv_summary,
    )
    _print_cover_letter(cover_letter)

    # Step 8: Save option
    _offer_save(job, cv_summary, cover_letter, confidence)


def _offer_save(job, summary: str, letter: str, confidence: int) -> None:
    print(_div())
    try:
        if input("  Save to file? (y/n): ").strip().lower() != "y":
            return
    except EOFError:
        return

    safe = (job.title or "job").replace(" ", "_").replace("/", "_")
    path = os.path.join(ROOT, f"application_{safe}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"JOB: {job.title}\nConfidence: {confidence}/100\n\n")
        f.write("=" * 60 + "\nCV SUMMARY\n" + "=" * 60 + "\n\n")
        f.write(summary + "\n\n")
        f.write("=" * 60 + "\nCOVER LETTER\n" + "=" * 60 + "\n\n")
        f.write(letter + "\n")
    print(f"\n  ✅  Saved: application_{safe}.txt")

    # Generate tailored CV PDF alongside the text file
    try:
        pdf_path = os.path.join(ROOT, f"cv_{safe}.pdf")
        generate_cv_pdf(base_cv, pdf_path, cv_summary=summary)
        print(f"  ✅  CV PDF : cv_{safe}.pdf")
    except Exception as e:
        print(f"  ⚠️  PDF skipped: {e}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print(_header("🏗️   CIVIL ENGINEERING JOB APPLICATION ASSISTANT"))

    # Show which AI provider is active — and diagnose .env loading
    groq_key      = os.environ.get("GROQ_API_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if groq_key:
        # Show first 8 chars of key so user can confirm it's the right one
        key_preview = groq_key[:12] + "..." if len(groq_key) > 12 else groq_key
        print(f"\n  AI provider : Groq — FREE ✓  (key: {key_preview})")
    elif anthropic_key:
        print(f"\n  AI provider : Anthropic Claude")
    else:
        print(f"\n  AI provider : Rule-based fallback")
        print(f"  ⚠️  No API key found. Check your .env file.")
        print(f"  Expected location: {os.path.join(ROOT, '.env')}")
        print(f"  Expected contents:  GROQ_API_KEY=gsk_your_key_here")

    try:
        base_cv = _load_cv()
    except FileNotFoundError:
        print(f"\n  ❌  CV not found: {CV_PATH}")
        sys.exit(1)

    profile = base_cv.get("profile", {})
    print(f"\n  Candidate : {profile.get('name', '?')}")
    print(f"  Experience: {profile.get('experience_years', '?')} years")

    while True:
        raw_text = _get_job_description()
        if not raw_text:
            print("\n  No text entered. Exiting.")
            break

        process_job_description(raw_text, base_cv)

        print()
        try:
            if input("  Process another job? (y/n): ").strip().lower() != "y":
                print("\n  Done. Good luck! 🍀\n")
                break
        except EOFError:
            break


if __name__ == "__main__":
    main()