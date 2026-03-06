# civil_engineering/job_parser.py
import re
from civil_engineering.domain.job import ParsedJob

ROLE_KEYWORDS = {
    # Compound/specific titles first — longer patterns matched before shorter ones
    "Civil Construction Engineer": ["civil construction engineer"],
    "Structural Design Engineer":  ["structural design engineer"],
    "Site Engineer":               ["site engineer"],
    "Civil Engineer":              ["civil engineer"],
    "Structural Engineer":         ["structural engineer"],
    "Project Engineer":            ["project engineer"],
    "Construction Manager":        ["construction manager"],
    "Resident Engineer":           ["resident engineer"],
    "Infrastructure Engineer":     ["infrastructure engineer"],
    "Graduate Engineer":           ["graduate engineer", "grad engineer"],
    "Senior Engineer":             ["senior engineer", "senior civil", "senior site"],
    "Principal Engineer":          ["principal engineer"],
    "Quantity Surveyor":           ["quantity surveyor", "qs "],
    "Site Manager":                ["site manager"],
    "Project Manager":             ["project manager"],
}

PROJECT_KEYWORDS = {
    "Buildings":      ["building", "residential", "commercial", "housing", "office block",
                       "mid-rise", "high-rise"],
    "Infrastructure": ["infrastructure", "road", "highway", "bridge construction",
                       "drainage", "rail", "railway", "piling", "pile"],
    "Construction":   ["construction", "concrete", "reinforced concrete", "rebar",
                       "cage fabrication", "pre-piling", "formwork", "structural works"],
    "Industrial":     ["industrial", "factory", "warehouse", "manufacturing"],
    "Water & Sewage": ["sewage", "wastewater", "water treatment"],
    "Refinery":       ["refinery", "petrochemical", "offshore"],
    "Energy":         ["power station", "solar farm", "wind farm", "power plant"],
}

SKILL_KEYWORDS = [
    "autocad", "revit", "civil 3d", "staad", "robot", "etabs", "prokon",
    "protastructure", "prota software", "tekla", "navisworks",
    "primavera", "ms project", "microsoft project",
    "cscs", "smsts", "sssts", "iosh", "nebosh", "coren",
    "hse", "qa/qc", "site supervision", "setting out", "bim",
    "structural design", "drainage design", "quantity surveying",
    "reinforced concrete", "steel", "formwork", "earthworks",
    "rebar", "reinforcement", "concrete production",
    "stakeholder", "report writing", "team management",
]


def _extract_title(text: str) -> str | None:
    """
    Extract job title using three strategies in order of reliability:

    1. Look for explicit 'Job Title:' label — most reliable
       Handles: 'Job Title: Project EngineerReports To:...' (no newline)

    2. Look for '[Title] at [Company]' pattern
       Handles: 'Construction Manager at Credun Limited'

    3. Keyword scan of opening 500 chars, then full text
       Handles: everything else

    WHY LABEL DETECTION FIRST?
    When text is pasted from a website it often loses newlines, turning
    'Job Title: Project Engineer\nReports To: ...' into
    'Job Title: Project EngineerReports To: ...'
    A keyword scan would find 'engineer' in 'Reports To' before finding
    the actual title. The label pattern finds it immediately.
    """
    # Strategy 1: explicit 'Job Title:' label
    label_match = re.search(
        r'job\s*title\s*[:\-]\s*([A-Za-z ()\/]+?)(?:reports|location|industry|\n|$)',
        text, re.IGNORECASE
    )
    if label_match:
        raw = label_match.group(1).strip()
        # Match the extracted text against known roles
        raw_lower = raw.lower()
        for role, patterns in ROLE_KEYWORDS.items():
            for pattern in patterns:
                if pattern in raw_lower:
                    return role
        # If no known role matched but we got a clean title, return it directly
        if len(raw) < 50:
            return raw.title()

    # Strategy 2: '[Title] at [Company]' pattern
    at_match = re.search(
        r'^([A-Za-z ()\/]+?)\s+at\s+[A-Z]',
        text.strip(), re.MULTILINE
    )
    if at_match:
        raw = at_match.group(1).strip().lower()
        for role, patterns in ROLE_KEYWORDS.items():
            for pattern in patterns:
                if pattern in raw:
                    return role

    # Strategy 3: keyword scan — opening section first, then full text
    text_lower = text.lower()
    # Avoid matching titles from within 'construction/site engineering experience'
    # by only scanning for titles, not inside compound phrases
    opening = text_lower[:500]

    for role, patterns in ROLE_KEYWORDS.items():
        for pattern in patterns:
            # Check pattern is not immediately preceded/followed by '/'
            idx = opening.find(pattern)
            if idx != -1:
                before = opening[idx-1] if idx > 0 else ' '
                after  = opening[idx+len(pattern)] if idx+len(pattern) < len(opening) else ' '
                # Reject if followed by 's' (plural) or preceded/followed by /
                if before not in '/\\' and after not in '/\\s':
                    return role

    for role, patterns in ROLE_KEYWORDS.items():
        for pattern in patterns:
            idx = text_lower.find(pattern)
            if idx != -1:
                before = text_lower[idx-1] if idx > 0 else ' '
                after  = text_lower[idx+len(pattern)] if idx+len(pattern) < len(text_lower) else ' '
                if before not in '/\\' and after not in '/\\s':
                    return role

    return None


def _extract_years(text: str) -> int | None:
    """
    Extract years of experience required — not company history.
    Looks for requirement-context patterns first, then smallest value.
    """
    text_lower = text.lower()

    requirement_patterns = [
        r'(\d+)\+?\s*years?\s+of\s+relevant',
        r'minimum\s+(?:of\s+)?(\d+)\+?\s*years?',
        r'at\s+least\s+(\d+)\+?\s*years?',
        r'(\d+)\s*[-–]\s*\d+\s*years?\s+(?:of\s+)?(?:relevant\s+)?experience',
        r'(\d+)\+\s*years?\s+(?:relevant\s+)?(?:construction|site|engineering)',
    ]
    for pattern in requirement_patterns:
        m = re.search(pattern, text_lower)
        if m:
            return int(m.group(1))

    # Look in requirements section specifically
    for marker in ["requirements", "qualifications", "what we need"]:
        idx = text_lower.find(marker)
        if idx != -1:
            section = text_lower[idx:idx+500]
            m = re.search(r'(\d+)\+?\s*years?', section)
            if m:
                return int(m.group(1))

    # Last resort: smallest number near 'years' (avoids company history years)
    candidates = [int(x) for x in re.findall(r'(\d+)\+?\s*years?', text_lower)
                  if 1 <= int(x) <= 20]
    return min(candidates) if candidates else None


def _extract_project_types(text: str) -> list[str]:
    """Detect project types from job description section, skipping company intro."""
    text_lower  = text.lower()
    job_section = text_lower

    for marker in ["job description", "job brief", "key responsibilities",
                   "responsibilities", "about the role"]:
        idx = text_lower.find(marker)
        if idx != -1:
            job_section = text_lower[idx:]
            break

    found = []
    for project_type, keywords in PROJECT_KEYWORDS.items():
        for kw in keywords:
            if kw in job_section:
                found.append(project_type)
                break
    return found


def _extract_salary(text: str) -> str | None:
    """Extract salary — handles ₦, £, and plain number ranges."""
    naira = re.search(
        r'(?:salary\s*[:\-]?\s*)?[₦#]?\s*(\d[\d,]*k?)\s*[-–]\s*(\d[\d,]*k?)\s*(?:net|gross|monthly|per\s*month)?',
        text, re.IGNORECASE
    )
    if naira and int(re.sub(r'[,k]','',naira.group(1)).replace('k','000') or '0') > 10000:
        return f"₦{naira.group(1)} – ₦{naira.group(2)}"

    pound = re.search(r'£[\d,]+k?\s*[-–to]+\s*£[\d,]+k?', text, re.IGNORECASE)
    if pound:
        return pound.group(0)

    # Plain "600,000 Monthly" or "₦600,000"
    plain = re.search(r'[₦#]?\s*(\d{3}[\d,]+)\s*(?:monthly|per month|net)', text, re.IGNORECASE)
    if plain:
        return f"₦{plain.group(1)}"

    if "competitive" in text.lower():
        return "Competitive"
    return None


def _extract_skills(text: str) -> list[str]:
    text_lower = text.lower()
    return [s for s in SKILL_KEYWORDS if s in text_lower]


def _extract_location(text: str) -> str | None:
    patterns = [
        r'location[:\s]+([A-Za-z][A-Za-z\s,]+?)(?:\n|\.|\||job type|industry)',
        r'based in[:\s]+([A-Za-z][A-Za-z\s,]+?)(?:\n|\.)',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            loc = m.group(1).strip().rstrip(',')
            if len(loc) < 60:
                return loc
    return None


def _extract_company(text: str) -> str | None:
    m = re.search(
        r'(?:about company|company name)[:\s]+([A-Za-z][A-Za-z\s&,.-]+?)(?:\n|is a|specialise)',
        text, re.IGNORECASE
    )
    if m:
        name = m.group(1).strip()
        if len(name) < 80:
            return name
    # Also try '[Title] at [Company]' format
    at_m = re.search(r'\bat\s+([A-Z][A-Za-z\s&]+(?:Ltd|Limited|Inc|Consulting|Group)?)', text)
    if at_m:
        return at_m.group(1).strip()
    return None


def _extract_email(text):
    """Extract any email address found in the job description."""
    import re as _re
    m = _re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+[.][a-zA-Z]{2,}', text)
    return m.group(0) if m else None
def parse_job_description(text: str) -> ParsedJob:
    """Parse raw job description text into a structured ParsedJob."""
    job = ParsedJob()
    job.title           = _extract_title(text)
    job.years_required  = _extract_years(text)
    job.project_types   = _extract_project_types(text)
    job.salary          = _extract_salary(text)
    job.required_skills = _extract_skills(text)
    job.location        = _extract_location(text)
    job.company         = _extract_company(text)
    job.apply_email     = _extract_email(text)
    job.raw_text        = text
    if not job.title:
        job.title = "Engineer"
    return job
