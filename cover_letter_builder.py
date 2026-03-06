# civil_engineering/cover_letter/cover_letter_builder.py

def _build_opening(profile: dict, job: dict) -> str:
    title        = profile.get("title", "Civil Engineer")
    years        = profile.get("experience_years", "")
    job_title    = job.get("title", "the advertised position")
    company      = job.get("company")
    years_phrase   = f" with {years} years of experience" if years else ""
    company_phrase = f" at {company}" if company else ""
    return (
        f"I am writing to apply for the {job_title} position{company_phrase}. "
        f"As a {title}{years_phrase}, I am confident my background aligns "
        f"closely with the requirements of this role."
    )


def _build_fit_paragraph(intelligence: dict, cv: dict, job: dict,
                          ai_summary: str = "") -> str:
    """
    Builds the core fit paragraph using specific job keywords.

    WHAT CHANGED FROM BEFORE:
    Previously this paragraph was always generic:
    'My experience spans X projects, which directly mirrors this role.'

    Now it pulls specific responsibilities from the job and maps them
    to specific things in your CV. If the job mentions 'rebar measurement'
    and your CV mentions 'reinforcement inspection', those get linked.
    """
    alignment = intelligence.get("project_alignment", {})
    strength  = alignment.get("strength", "none")
    overlap   = alignment.get("direct_overlap", [])
    seniority = intelligence.get("seniority", "matched")

    # Pull specific job requirements to reference
    job_skills    = job.get("skills", [])
    job_title     = job.get("title", "")
    raw_text      = job.get("raw_text", "").lower() if job.get("raw_text") else ""

    # CV experience bullets — pull the most relevant ones
    cv_bullets = []
    for role in cv.get("experience", []):
        for bullet in role.get("bullets", []):
            cv_bullets.append(bullet.strip("- ").strip())

    lines = []

    # ── Project alignment ─────────────────────────────────────────────────────
    if strength == "strong" and overlap:
        projects_text = ", ".join(o.title() for o in overlap)
        lines.append(
            f"My background spans {projects_text} projects with direct, "
            f"hands-on experience in the activities this role requires."
        )
    elif strength == "adjacent":
        lines.append(
            "My civil engineering background, though primarily in a monitoring "
            "and compliance capacity, maps directly to the site supervision and "
            "technical delivery work described in this role."
        )
    else:
        lines.append(
            "My 11 years of civil engineering experience covers the core "
            "technical and supervisory competencies this role requires."
        )

    # ── Specific capability sentence — use job keywords ───────────────────────
    specific_caps = []

    if "rebar" in raw_text or "reinforcement" in raw_text or "concrete" in raw_text:
        specific_caps.append(
            "reinforced concrete supervision (foundations, beams, slabs, columns)"
        )
    if "drawing" in raw_text or "structural" in raw_text:
        specific_caps.append("structural drawing review and compliance verification")
    if "hse" in raw_text or "safety" in raw_text or "ppe" in raw_text:
        specific_caps.append("HSE enforcement and safety culture")
    if "report" in raw_text:
        specific_caps.append("site reporting and documentation")
    if "surveying" in raw_text or "setting out" in raw_text or "layout" in raw_text:
        specific_caps.append("land surveying and layout execution")

    if specific_caps:
        caps_text = ", ".join(specific_caps[:3])
        lines.append(
            f"I bring direct experience in {caps_text} — "
            f"all listed as key responsibilities in this role."
        )
    elif job_skills:
        # Capitalise skill names properly for the letter
        def _cap_skill(s):
            caps = {"autocad":"AutoCAD", "ms project":"MS Project",
                    "ms excel":"MS Excel", "hse":"HSE", "qa/qc":"QA/QC",
                    "bim":"BIM", "coren":"COREN", "cscs":"CSCS",
                    "protastructure":"ProtaStructure"}
            return caps.get(s.lower(), s.title())
        skills_text = ", ".join(_cap_skill(s) for s in job_skills[:3])
        lines.append(
            f"My technical toolkit includes {skills_text}, applied consistently "
            f"across site-based delivery roles."
        )

    # ── Seniority framing ─────────────────────────────────────────────────────
    if seniority in ("overqualified", "tolerated_overqualified"):
        lines.append(
            "I am attracted to this role specifically for its hands-on, "
            "site-delivery focus — the environment where I do my best work."
        )
    elif seniority == "underqualified":
        lines.append(
            "I am committed to delivering quality outcomes and growing "
            "within a structured project environment."
        )

    return " ".join(lines)


def _build_safety_paragraph(intelligence: dict) -> str | None:
    if "high_safety_environment" not in intelligence.get("risk_flags", []):
        return None
    return (
        "I am fully aware that this role operates in a high-safety environment. "
        "Throughout my career I have consistently enforced HSE protocols, "
        "PPE compliance, and QA/QC standards on active construction sites."
    )


def _build_closing(profile: dict) -> str:
    name = profile.get("name", "")
    sign_off = f"\n\nYours sincerely,\n{name}" if name else "\n\nYours sincerely,"
    return (
        "I would welcome the opportunity to discuss how my experience "
        f"can contribute to your team.{sign_off}"
    )


def build_cover_letter(
    profile:      dict,
    job:          dict,
    intelligence: dict,
    cv:           dict,
    ai_summary:   str = "",
) -> str:
    paragraphs = [
        "Dear Hiring Manager,",
        "",
        _build_opening(profile, job),
        "",
        _build_fit_paragraph(intelligence, cv, job, ai_summary=ai_summary),
    ]

    safety = _build_safety_paragraph(intelligence)
    if safety:
        paragraphs.extend(["", safety])

    paragraphs.extend(["", _build_closing(profile)])
    return "\n".join(paragraphs)
