# civil_engineering/cv_parser.py
#
# Parses a CV PDF into the same structured format as cv.json.
# This is the commercial unlock — any engineer can upload their CV
# and get tailored applications without manual data entry.
#
# APPROACH:
# 1. Extract raw text from PDF (pypdf)
# 2. Split into sections by common CV headers
# 3. Parse each section with targeted regex and heuristics
# 4. Return a dict matching the cv.json schema
#
# WHY NOT USE AI FOR THIS?
# Parsing is deterministic — headers like "PROFESSIONAL EXPERIENCE"
# always appear, dates always follow the same patterns, bullet points
# always start with "•" or "-". Regex is faster, cheaper, and more
# reliable than asking an AI to read a CV.
# We DO use AI for the summary (cv_tailor.py) — that's creative work.

import re
import os
from pypdf import PdfReader


# ── Section header patterns ────────────────────────────────────────────────────
# These are the most common CV section names we'll encounter

SECTION_HEADERS = [
    'professional summary', 'summary', 'profile', 'career objective', 'objective',
    'professional experience', 'experience', 'work experience', 'employment',
    'education', 'academic background',
    'skills', 'technical skills', 'design & engineering tools', 'tools',
    'structural engineering knowledge', 'engineering knowledge', 'knowledge',
    'training', 'structural design training', 'certifications', 'courses',
    'projects', 'key projects',
    'references',
    # Common Nigerian CV sections that are NOT useful content
    'personal information', 'personal details', 'personal data',
    'contact information', 'contact details', 'bio data', 'biodata',
    'declaration', 'personal statement',
]

# Skills we recognise for civil engineers
KNOWN_SKILLS = [
    'autocad', 'revit', 'civil 3d', 'staad', 'robot', 'etabs', 'prokon',
    'protastructure', 'prota software', 'tekla', 'navisworks', 'bim',
    'primavera', 'ms project', 'microsoft project', 'ms excel', 'excel',
    'power bi', 'python', 'matlab',
    'cscs', 'smsts', 'sssts', 'iosh', 'nebosh', 'coren',
    'hse', 'qa/qc', 'site supervision', 'setting out',
    'reinforced concrete', 'structural design', 'quantity surveying',
    'drainage design', 'autocad plant 3d', 'ProtaStructure',
]


# ── Text extraction ────────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a PDF file."""
    reader = PdfReader(pdf_path)
    pages  = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return '\n'.join(pages)


def extract_text_from_bytes(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes (for web upload)."""
    import io
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages  = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return '\n'.join(pages)


# ── Section splitting ─────────────────────────────────────────────────────────

def _split_sections(text: str) -> dict:
    """
    Split CV text into named sections.

    Strategy: find lines that match known section headers (ALL CAPS or
    Title Case), use them as boundaries, collect everything between.

    WHY CHECK FOR ALL CAPS?
    Most CV section headers are written in ALL CAPS or Title Case with
    no punctuation. A line like "PROFESSIONAL EXPERIENCE" or
    "Professional Experience" is almost certainly a section header.
    Body text lines are rarely ALL CAPS.
    """
    lines    = text.split('\n')
    sections = {}
    current  = 'header'
    buffer   = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            buffer.append('')
            continue

        # Check if this line is a section header
        lower = stripped.lower().rstrip(':').strip()
        is_header = (
            lower in SECTION_HEADERS
            or any(lower.startswith(h) for h in SECTION_HEADERS)
        )

        # Treat ALL CAPS short lines as headers ONLY if they contain
        # a known header keyword — avoids treating names as headers
        if (stripped.isupper() and 3 < len(stripped) < 60
                and not stripped.startswith('•')
                and any(h in stripped.lower() for h in SECTION_HEADERS)):
            is_header = True

        if is_header:
            # Save previous section
            sections[current] = '\n'.join(buffer).strip()
            current = lower
            buffer  = []
        else:
            buffer.append(line)

    sections[current] = '\n'.join(buffer).strip()
    return sections


# ── Header parsing (name, title, contact) ─────────────────────────────────────

def _parse_header(header_text: str) -> dict:
    """
    Extract name, title, location, phone, email, LinkedIn from the
    top section of the CV (before first section header).
    Skips common document-title phrases like "Curriculum Vitae",
    "Personal Information" etc. that appear on many Nigerian CVs.
    """
    NOT_CONTENT = {
        'curriculum vitae', 'cv', 'resume', 'résumé', 'biodata', 'bio data',
        'personal profile', 'professional profile', 'my curriculum vitae',
        'updated cv', 'cover letter', 'application letter',
        'personal information', 'personal details', 'personal data',
        'contact information', 'contact details', 'declaration',
        'name', 'email', 'phone', 'address', 'date of birth',
        'nationality', 'state of origin', 'lga', 'sex', 'gender',
        'marital status',
    }

    def _skip(line):
        l = line.lower().strip()
        return (l in NOT_CONTENT
                or l.startswith('curriculum')
                or l.startswith('resume')
                or '@' in l
                or bool(re.search(r'\d{5,}', l)))

    lines  = [l.strip() for l in header_text.split('\n') if l.strip()]
    result = {}

    # First non-skippable line that looks like a name (2+ words, no digits)
    for line in lines:
        if (not _skip(line)
                and len(line.split()) >= 2
                and not re.search(r'\d', line)
                and len(line) < 60):
            result['name'] = line
            break

    # Next non-skippable, non-name short line is the job title
    name_seen = False
    for line in lines:
        if _skip(line):
            continue
        if not name_seen:
            name_seen = True
            continue
        if len(line.split()) <= 8 and not re.search(r'\d{4}', line):
            result['title'] = line.split('|')[0].strip()
            break

    # Contact fields — scan all text
    full = '\n'.join(lines)
    m = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', full)
    if m: result['email'] = m.group(0)

    m = re.search(r'(?:\+?234|0)\d{10}|\+44\s?\d{10}', full)
    if m: result['phone'] = m.group(0).strip()

    m = re.search(r'linkedin\.com/in/[\w-]+', full, re.IGNORECASE)
    if m: result['linkedin'] = m.group(0)

    m = re.search(
        r'(?:Lagos|Abuja|Port Harcourt|Ibadan|Kano|Enugu|London|UK)[,\s]*(?:Nigeria|State)?',
        full, re.IGNORECASE)
    if m: result['location'] = m.group(0).strip().rstrip(',')

    return result

# ── Experience parsing ─────────────────────────────────────────────────────────

def _parse_experience(exp_text: str) -> list:
    """
    Parse the experience section into a list of role dicts.

    Structure we expect:
        Role Title
        Company Name, Location  YYYY – YYYY
        • Bullet point
        • Bullet point
    """
    if not exp_text:
        return []

    roles   = []
    lines   = exp_text.split('\n')
    current = None

    # Date pattern: "2020 – Present" or "2018 – 2020" or "2018-2020"
    DATE_RE = re.compile(r'\b(20\d{2}|19\d{2})\s*[–\-—]\s*(20\d{2}|Present|present|current)\b')

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if not line:
            i += 1
            continue

        date_match = DATE_RE.search(line)

        if date_match:
            # Save any current role before starting a new one
            if current and (current.get('bullets') or current.get('company')):
                roles.append(current)

            # Everything before the date is "Role – Company" or just company
            before_date = line[:date_match.start()].strip().rstrip('|,–- ')

            # Check for role–company separator: "–", "|", "-" between role and company
            # Pattern: "Role Title – Company Name" or "Role Title | Company"
            INLINE_SEP = re.compile(r'\s+[–|]\s+')
            sep_match  = INLINE_SEP.search(before_date)

            if sep_match:
                role_part    = before_date[:sep_match.start()].strip()
                company_part = before_date[sep_match.end():].strip()
            else:
                # No separator — treat whole thing as company, look back for role
                prev = lines[i-1].strip() if i > 0 else ''
                role_part    = prev if prev and not DATE_RE.search(prev) else before_date
                company_part = before_date if sep_match is None else ''

            current = {
                'role':     role_part,
                'company':  company_part,
                'period':   date_match.group(0),
                'location': '',
                'bullets':  [],
            }

        elif line.startswith(('•', '-', '–', '*')) or line.startswith('  •'):
            # Bullet point
            bullet_text = line.lstrip('•–-* \t').strip()
            if bullet_text and current is not None:
                current['bullets'].append(f'- {bullet_text}')

        else:
            # Could be a role title (no date, not a bullet)
            # Check if next line has a date — confirms this is a role title
            next_line = lines[i+1].strip() if i+1 < len(lines) else ''
            next_has_date = bool(DATE_RE.search(next_line))

            if next_has_date:
                # Save current role and start new
                if current and (current.get('bullets') or current.get('company')):
                    roles.append(current)
                current = {
                    'role':     line,
                    'company':  '',
                    'period':   '',
                    'location': '',
                    'bullets':  [],
                }
            # Otherwise it's continuation text — skip

        i += 1

    # Don't forget the last role
    if current and (current.get('bullets') or current.get('company')):
        roles.append(current)

    return roles


# ── Education parsing ──────────────────────────────────────────────────────────

def _parse_education(edu_text: str) -> list:
    """Parse education section into list of degree dicts."""
    if not edu_text:
        return []

    education = []
    lines     = [l.strip() for l in edu_text.split('\n') if l.strip()]
    YEAR_RE   = re.compile(r'\b(20\d{2}|19\d{2})\b')

    i = 0
    while i < len(lines):
        line = lines[i]

        # Skip bullet points and short lines
        if line.startswith(('•', '-', '*')) or len(line) < 10:
            i += 1
            continue

        year_match = YEAR_RE.search(line)

        # Lines with degree keywords
        degree_keywords = ['bachelor', 'b.eng', 'b.sc', 'bsc', 'hnd', 'master',
                           'm.sc', 'msc', 'phd', 'diploma', 'certificate',
                           'higher national', 'ordinary national']
        is_degree = any(kw in line.lower() for kw in degree_keywords)

        if is_degree:
            # Extract year from this line or next
            year = year_match.group(0) if year_match else ''
            if not year and i+1 < len(lines):
                next_match = YEAR_RE.search(lines[i+1])
                if next_match:
                    year = next_match.group(0)

            # Institution is usually next line if not on same line
            institution = ''
            if i+1 < len(lines) and not lines[i+1].startswith(('•', '-')):
                institution = lines[i+1].strip()
                # Remove trailing year from institution
                institution = YEAR_RE.sub('', institution).strip().rstrip('–-').strip()

            education.append({
                'degree':      line.strip(),
                'institution': institution,
                'year':        year,
            })

        i += 1

    return education


# ── Skills parsing ────────────────────────────────────────────────────────────

def _parse_skills(skills_text: str, full_text: str) -> list:
    """
    Extract skills from the skills section AND scan full CV text
    for known engineering tools.
    """
    found = set()
    combined = (skills_text + '\n' + full_text).lower()

    for skill in KNOWN_SKILLS:
        if skill.lower() in combined:
            # Normalise capitalisation
            caps_map = {
                'autocad': 'AutoCAD', 'protastructure': 'ProtaStructure',
                'ms excel': 'MS Excel', 'excel': 'MS Excel',
                'ms project': 'MS Project', 'microsoft project': 'MS Project',
                'power bi': 'Power BI', 'hse': 'HSE', 'qa/qc': 'QA/QC',
                'bim': 'BIM', 'coren': 'COREN', 'python': 'Python',
                'prota software': 'ProtaStructure',
                'autocad plant 3d': 'AutoCAD Plant 3D',
            }
            found.add(caps_map.get(skill.lower(), skill.title()))

    # Also extract bullet-listed skills from the skills section
    for line in skills_text.split('\n'):
        line = line.lstrip('•–-* ').strip()
        if '–' in line:
            # "ProtaStructure – Structural modeling..." → take first part
            skill_name = line.split('–')[0].strip()
            if 3 < len(skill_name) < 30:
                found.add(skill_name)

    return sorted(found)


# ── Years of experience ────────────────────────────────────────────────────────

def _estimate_years(experience: list, education: list = None) -> int:
    """
    Estimate total years of professional experience.

    Takes the earliest START year found in experience roles.
    Education years are excluded — we count professional work, not study.
    """
    import datetime
    current_year = datetime.datetime.now().year

    start_years = []
    YEAR_RE     = re.compile(r'\b(20\d{2}|19\d{2})\b')

    for role in experience:
        period  = role.get('period', '')
        matches = YEAR_RE.findall(period)
        if matches:
            start_years.append(int(matches[0]))   # first year = start year

    if not start_years:
        return 0

    earliest = min(start_years)
    total    = current_year - earliest
    return max(0, min(total, 40))


# ── Structural knowledge ──────────────────────────────────────────────────────

def _parse_knowledge(text: str) -> list:
    """Extract structural knowledge bullet points."""
    if not text:
        return []
    items = []
    for line in text.split('\n'):
        line = line.lstrip('•–-* ').strip()
        if len(line) > 10:
            items.append(line)
    return items


# ── Main public function ──────────────────────────────────────────────────────

def parse_cv_pdf(pdf_path: str) -> dict:
    """
    Parse a CV PDF into a structured dict matching the cv.json schema.

    Args:
        pdf_path: Path to the CV PDF file

    Returns:
        Dict with keys: profile, experience, education, skills,
                        structural_knowledge, project_types
    """
    raw_text = extract_text_from_pdf(pdf_path)
    return _parse_cv_text(raw_text)


def parse_cv_bytes(pdf_bytes: bytes) -> dict:
    """
    Parse a CV PDF from bytes (for web upload handler).
    Same as parse_cv_pdf but accepts bytes instead of a file path.
    """
    raw_text = extract_text_from_bytes(pdf_bytes)
    return _parse_cv_text(raw_text)


def _parse_cv_text(raw_text: str) -> dict:
    """Core parsing logic — works on extracted text."""
    sections = _split_sections(raw_text)

    # Find the right section keys
    def _get(keys):
        for k in keys:
            for sk, sv in sections.items():
                if k in sk:
                    return sv
        return ''

    header_text = sections.get('header', '')
    exp_text    = _get(['experience', 'employment'])
    edu_text    = _get(['education', 'academic'])
    skills_text = _get(['skills', 'tools'])
    know_text   = _get(['knowledge'])
    summary_text = _get(['summary', 'profile', 'objective'])

    profile    = _parse_header(header_text)
    experience = _parse_experience(exp_text)
    education  = _parse_education(edu_text)
    skills     = _parse_skills(skills_text, raw_text)
    knowledge  = _parse_knowledge(know_text)
    years      = _estimate_years(experience)

    if years:
        profile['experience_years'] = years

    # Infer project types from experience bullets
    all_bullets = ' '.join(
        b for role in experience for b in role.get('bullets', [])
    ).lower()

    project_types = []
    if any(w in all_bullets for w in ['foundation', 'column', 'slab', 'beam', 'concrete']):
        project_types.append('construction')
    if any(w in all_bullets for w in ['building', 'residential', 'commercial']):
        project_types.append('buildings')
    if any(w in all_bullets for w in ['road', 'infrastructure', 'drainage', 'bridge']):
        project_types.append('infrastructure')
    if not project_types:
        project_types = ['construction']  # default for civil engineers

    return {
        'profile':              profile,
        'experience':           experience,
        'education':            education,
        'skills':               skills,
        'structural_knowledge': knowledge,
        'project_types':        project_types,
        'summary':              summary_text,
        '_raw_text':            raw_text,   # keep for debugging
    }


# ── Quality scoring ────────────────────────────────────────────────────────────

def cv_parse_quality(cv: dict) -> dict:
    """
    Score the quality of a parsed CV so the UI can warn if parsing was poor.
    Returns: {score: 0-100, warnings: [...]}
    """
    warnings = []
    score    = 100

    profile = cv.get('profile', {})
    if not profile.get('name') or profile.get('name') == 'Unknown':
        warnings.append("Could not extract your name — please check the output")
        score -= 20
    if not profile.get('email'):
        warnings.append("No email found in CV")
        score -= 10
    if not cv.get('experience'):
        warnings.append("No work experience extracted — CV format may be unusual")
        score -= 30
    if not cv.get('skills'):
        warnings.append("No skills extracted")
        score -= 15
    if not cv.get('education'):
        warnings.append("No education found")
        score -= 10
    if not profile.get('experience_years', 0):
        warnings.append("Years of experience not detected — will be estimated from job dates")
        score -= 5

    return {'score': max(0, score), 'warnings': warnings}