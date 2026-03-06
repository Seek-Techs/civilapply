# civil_engineering/cv_reader.py
#
# Reads any civil engineer's CV PDF and extracts a structured profile.
# This is the commercial unlock — instead of one hardcoded cv.json,
# any engineer can upload their CV and get personalised output.
#
# PIPELINE:
# 1. pdfplumber  — extract raw text from PDF (handles any layout)
# 2. Rule-based  — extract name, email, phone, years (fast, reliable)
# 3. Cohere AI   — extract experience, skills, education from free text
#                  (handles infinite CV format variations)
# 4. Fallback    — if AI fails, return what rule-based found
#
# OUTPUT: a dict matching the cv.json schema so the rest of the
# pipeline works without any changes.

import re
import os
import json
import urllib.request
import urllib.error


# ── Step 1: Extract raw text from PDF ────────────────────────────────────────

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a PDF file using pdfplumber."""
    try:
        import pdfplumber
        text = ''
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + '\n'
        return text.strip()
    except ImportError:
        raise RuntimeError("pdfplumber not installed. Run: pip install pdfplumber")
    except Exception as e:
        raise RuntimeError(f"Could not read PDF: {e}")


# ── Step 2: Rule-based field extraction ──────────────────────────────────────

def _extract_email(text: str) -> str:
    m = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    return m.group(0) if m else ''

def _extract_phone(text: str) -> str:
    m = re.search(r'(?:\+?234|0)[789][01]\d{8}', text)
    return m.group(0) if m else ''

def _extract_linkedin(text: str) -> str:
    m = re.search(r'linkedin\.com/in/[A-Za-z0-9\-]+', text, re.IGNORECASE)
    return m.group(0) if m else ''

def _extract_name(text: str) -> str:
    """
    Extract candidate name from CV text.
    Skips: document titles, section headers, contact field labels,
    and "Name: John Doe" patterns (extracts value after colon).
    """
    NOT_A_NAME = {
        'curriculum vitae', 'cv', 'resume', 'biodata', 'bio data',
        'personal profile', 'professional profile', 'my curriculum vitae',
        'updated cv', 'cover letter', 'application letter',
        'personal information', 'personal details', 'personal data',
        'contact information', 'contact details', 'declaration',
    }

    for line in text.split('\n'):
        line = line.strip()
        if not line or len(line) > 60:
            continue
        low = line.lower()

        # Skip known non-name lines
        if low in NOT_A_NAME:
            continue
        if low.startswith('curriculum') or low.startswith('resume'):
            continue
        if '@' in line or 'linkedin' in low:
            continue

        # Strip leading bullet characters (•, -, *, ·) common in Nigerian CVs
        clean = line.lstrip('•·*- ').strip()
        low_clean = clean.lower()

        # Handle "Name: John Doe" or "Full Name: John Doe" patterns
        if (low_clean.startswith('name:') or low_clean.startswith('full name:')
                or low_clean.startswith('full name :')):
            value = clean.split(':', 1)[1].strip()
            if value and len(value.split()) >= 2 and not re.search(r'\d', value):
                return value
            continue

        # Skip lines that are clearly contact/metadata fields
        if re.match(r'^(email|phone|tel|address|dob|date of birth|sex|gender|state|lga|nationality|marital)\s*:', low):
            continue

        # Strip leading bullet characters before final name check
        clean = line.lstrip('•·*- ').strip()
        # Must look like a name: 2+ words, no digits, reasonable length
        if (len(clean.split()) >= 2
                and not re.search(r'\d', clean)
                and len(clean) < 55
                and clean.lower() not in NOT_A_NAME):
            return clean

    return ''

def _extract_years_experience(text: str) -> int:
    """
    Calculate total years of experience from employment date ranges.
    Strategy 1: find earliest start year from job date ranges.
    Strategy 2: look for explicit "X years experience" phrases.
    Takes whichever gives a larger number.
    """
    import datetime
    current_year = datetime.datetime.now().year
    candidates   = []

    # Strategy 1: earliest employment year → now
    date_ranges = re.findall(
        r'(\d{4})\s*[\u2013\-\u2014]\s*(?:\d{4}|[Pp]resent|[Cc]urrent)', text
    )
    if date_ranges:
        earliest = min(int(yr) for yr in date_ranges)
        if 1990 <= earliest <= current_year:
            candidates.append(current_year - earliest)

    # Strategy 2: explicit "X years" phrases
    text_lower = text.lower()
    for p in [r'(\d+)\+?\s*years?\s+(?:of\s+)?(?:experience|work)',
              r'(\d+)\+?\s*years?\s+(?:in|across)']:
        for m in re.finditer(p, text_lower):
            val = int(m.group(1))
            if 1 <= val <= 40:
                candidates.append(val)

    return max(candidates) if candidates else 0

def _extract_title(text: str) -> str:
    """
    Extract professional title — skips document headers and section labels.
    Looks for lines containing known title keywords, then falls back to regex.
    """
    NOT_A_TITLE = {
        'curriculum vitae', 'cv', 'resume', 'biodata', 'bio data',
        'personal information', 'personal details', 'personal data',
        'personal profile', 'professional profile', 'contact information',
        'contact details', 'declaration', 'name', 'email', 'phone',
        'address', 'date of birth', 'nationality', 'state of origin',
        'sex', 'gender', 'marital status', 'lga',
    }
    TITLE_KEYWORDS = [
        'engineer', 'manager', 'director', 'coordinator', 'supervisor',
        'consultant', 'analyst', 'officer', 'technician', 'specialist',
    ]

    for line in text.split('\n'):
        line = line.strip()
        low  = line.lower()
        if (not line or low in NOT_A_TITLE
                or low.startswith('curriculum')
                or '@' in line
                or re.search(r'\d{4,}', line)):
            continue
        if any(kw in low for kw in TITLE_KEYWORDS) and len(line) < 60:
            return line.split('|')[0].strip()

    m = re.search(
        r'(?:Senior |Principal |Lead |Graduate |Site |Project )?'
        r'(?:Civil|Structural|Construction|Geotechnical) Engineer',
        text, re.IGNORECASE)
    if m:
        return m.group(0).strip()

    return 'Civil Engineer'

def _extract_location(text: str) -> str:
    """Look for Lagos, Abuja, Port Harcourt etc. near the top."""
    cities = ['Lagos', 'Abuja', 'Port Harcourt', 'Ibadan', 'Kano',
              'Enugu', 'Benin City', 'Kaduna', 'Ogun', 'Oyo']
    text_head = text[:500]
    for city in cities:
        if city.lower() in text_head.lower():
            # Try to get "Lagos, Nigeria" or just "Lagos"
            m = re.search(rf'{city}[,\s]+(?:Nigeria|State)?', text_head, re.IGNORECASE)
            if m:
                return m.group(0).strip().rstrip(',')
            return city + ', Nigeria'
    return 'Nigeria'


# ── Step 3: AI-powered structured extraction ──────────────────────────────────

EXTRACTION_PROMPT = """Extract structured information from this CV text.
Return ONLY valid JSON, no markdown, no extra text.

Required JSON structure:
{{
  "experience": [
    {{
      "role": "job title",
      "company": "company name",
      "location": "city, country",
      "period": "2020 – Present",
      "bullets": ["- Achievement or responsibility", "- Another one"]
    }}
  ],
  "education": [
    {{
      "degree": "full degree name",
      "institution": "university/polytechnic name",
      "year": "2025"
    }}
  ],
  "skills": ["skill1", "skill2", "skill3"],
  "structural_knowledge": ["knowledge item 1", "knowledge item 2"],
  "summary": "professional summary in 2-3 sentences"
}}

Rules:
- Extract ALL jobs from the experience section
- Skills should be software tools and technical competencies only
- structural_knowledge is structural/technical knowledge items (can be empty list if not present)
- summary: write a factual 2-sentence summary of the candidate based ONLY on what the CV says
- Return empty lists [] if a section is not found
- NEVER invent information not in the CV

CV TEXT:
{cv_text}"""


def _call_cohere_extract(cv_text: str, api_key: str) -> dict | None:
    """Call Cohere to extract structured data from CV text."""
    prompt = EXTRACTION_PROMPT.format(cv_text=cv_text[:4000])  # stay within token limit

    payload = json.dumps({
        "model":       "command-r-plus-08-2024",
        "messages":    [{"role": "user", "content": prompt}],
        "max_tokens":  1200,
        "temperature": 0.1,  # low temperature = more deterministic extraction
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.cohere.com/v2/chat',
        data=payload,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type':  'application/json',
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        raw = (data
               .get('message', {})
               .get('content', [{}])[0]
               .get('text', ''))

        # Strip markdown fences if present
        raw = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
        raw = re.sub(r'\s*```$', '', raw.strip(), flags=re.MULTILINE)

        return json.loads(raw)

    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        return None


def _rule_based_fallback(text: str) -> dict:
    """
    When AI extraction fails, delegate to cv_parser.py which has a
    proper section-based regex parser. Much better than returning empty lists.
    """
    try:
        from civil_engineering.cv_parser import _parse_cv_text
        parsed = _parse_cv_text(text)
        return {
            'experience':           parsed.get('experience', []),
            'education':            parsed.get('education', []),
            'skills':               parsed.get('skills', []),
            'structural_knowledge': parsed.get('structural_knowledge', []),
            'summary':              parsed.get('summary', ''),
        }
    except Exception:
        return {
            'experience':           [],
            'education':            [],
            'skills':               [],
            'structural_knowledge': [],
            'summary':              '',
        }


# ── Step 4: Assemble final CV dict ────────────────────────────────────────────

def parse_cv_pdf(pdf_path: str) -> dict:
    """
    Main public function. Reads a CV PDF and returns a structured dict
    matching the cv.json schema used by the rest of the pipeline.

    Args:
        pdf_path: absolute or relative path to the CV PDF

    Returns:
        dict with keys: profile, experience, education, skills,
                        structural_knowledge
    """
    # ── Extract raw text ──────────────────────────────────────────────────
    raw_text = extract_text_from_pdf(pdf_path)
    if not raw_text:
        raise ValueError("Could not extract text from PDF. Is it a scanned image?")

    # ── Rule-based fields (fast, always available) ────────────────────────
    name     = _extract_name(raw_text)
    title    = _extract_title(raw_text)
    email    = _extract_email(raw_text)
    phone    = _extract_phone(raw_text)
    location = _extract_location(raw_text)
    linkedin = _extract_linkedin(raw_text)
    years    = _extract_years_experience(raw_text)

    # ── AI extraction (structured fields) ────────────────────────────────
    api_key  = os.environ.get('COHERE_API_KEY', '')
    ai_data  = None

    if api_key:
        ai_data = _call_cohere_extract(raw_text, api_key)

    if not ai_data:
        ai_data = _rule_based_fallback(raw_text)

    # ── Assemble final dict ───────────────────────────────────────────────
    return {
        'profile': {
            'name':               name,
            'title':              title,
            'experience_years':   years,
            'email':              email,
            'phone':              phone,
            'location':           location,
            'linkedin':           linkedin,
        },
        'project_types':        ['construction', 'buildings', 'infrastructure'],
        'experience':           ai_data.get('experience', []),
        'education':            ai_data.get('education', []),
        'skills':               ai_data.get('skills', []),
        'structural_knowledge': ai_data.get('structural_knowledge', []),
        'summary':              ai_data.get('summary', ''),
        '_source':              'uploaded_cv',
        '_raw_text':            raw_text[:2000],  # store for debugging
    }


def parse_cv_from_bytes(pdf_bytes: bytes, filename: str = 'cv.pdf') -> dict:
    """
    Parse a CV from raw bytes (used by web upload endpoint).
    Writes to a temp file, parses, cleans up.
    """
    import tempfile
    suffix = os.path.splitext(filename)[1] or '.pdf'
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    try:
        return parse_cv_pdf(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ── CV industry check ─────────────────────────────────────────────────────────

def detect_cv_industry(cv: dict) -> dict:
    """
    Detect if uploaded CV is for civil/structural engineering or something else.
    Returns: {is_civil: bool, confidence: int, detected: str, warning: str}

    WHY THIS MATTERS:
    Users might upload a software CV, marketing CV, etc. by mistake.
    Better to warn them immediately than let them generate wrong applications.
    """
    CIVIL_SIGNALS = [
        'civil', 'structural', 'construction', 'geotechnical', 'reinforced',
        'concrete', 'autocad', 'protastructure', 'site engineer', 'foundations',
        'piling', 'rebar', 'borehole', 'survey', 'topography', 'drainage',
        'road', 'bridge', 'infrastructure', 'coren', 'oau', 'unilag',
        'hse', 'qa/qc', 'primavera', 'ms project', 'building', 'slab', 'beam',
    ]
    SOFTWARE_SIGNALS = [
        'python', 'javascript', 'java', 'c#', '.net', 'react', 'node',
        'django', 'flask', 'sql', 'database', 'backend', 'frontend',
        'software engineer', 'developer', 'devops', 'kubernetes', 'docker',
        'machine learning', 'data science', 'android', 'ios', 'mobile',
        'asp.net', 'typescript', 'vue', 'angular', 'aws', 'azure',
    ]
    OTHER_SIGNALS = {
        'accounting':   ['accountant', 'audit', 'tax', 'ifrs', 'quickbooks', 'sage'],
        'medicine':     ['doctor', 'nurse', 'clinical', 'patient', 'hospital', 'mbbs'],
        'marketing':    ['marketing', 'brand', 'campaign', 'social media', 'seo', 'ads'],
        'law':          ['lawyer', 'barrister', 'solicitor', 'litigation', 'legal'],
    }

    # Build search text from CV
    text_parts = []
    profile = cv.get('profile', {})
    text_parts.append(profile.get('title', '').lower())
    text_parts.append(cv.get('summary', '').lower())
    for role in cv.get('experience', []):
        text_parts.append(role.get('role', '').lower())
        text_parts.append(role.get('company', '').lower())
        text_parts += [b.lower() for b in role.get('bullets', [])]
    text_parts += [s.lower() for s in cv.get('skills', [])]
    search = ' '.join(text_parts)

    civil_score    = sum(1 for s in CIVIL_SIGNALS    if s in search)
    software_score = sum(1 for s in SOFTWARE_SIGNALS if s in search)

    other_scores = {}
    for industry, signals in OTHER_SIGNALS.items():
        score = sum(1 for s in signals if s in search)
        if score > 0:
            other_scores[industry] = score

    # Decision
    if civil_score >= 2:
        return {'is_civil': True,  'confidence': min(100, civil_score * 12),
                'detected': 'civil_engineering', 'warning': ''}

    if software_score >= 2:
        return {'is_civil': False, 'confidence': min(100, software_score * 10),
                'detected': 'software',
                'warning': f'This looks like a software CV ({software_score} tech signals found). '
                           f'CivilApply is designed for civil engineers. '
                           f'Upload a civil engineering CV for best results.'}

    if other_scores:
        top = max(other_scores, key=other_scores.get)
        return {'is_civil': False, 'confidence': 40, 'detected': top,
                'warning': f'This CV looks like it may be for {top}, not civil engineering. '
                           f'Results may not be accurate.'}

    # Low signal either way — proceed with warning
    return {'is_civil': True, 'confidence': 30, 'detected': 'unknown',
            'warning': 'Could not clearly identify CV as civil engineering. '
                       'Check that your skills and experience are listed clearly.'}