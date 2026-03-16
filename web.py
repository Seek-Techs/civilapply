# web.py — Civil Engineering Job Application Web Interface
# Run: python web.py
# Open: http://localhost:5000

import sys, os, copy, json, traceback, time
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
# On Render, /data is a persistent disk. Locally, use project folder.
DATA_DIR = '/data' if os.path.isdir('/data') else ROOT
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── Load .env ─────────────────────────────────────────────────────────────────
def _load_env():
    path = os.path.join(ROOT, '.env')
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and v and k not in os.environ:
                os.environ[k] = v
    print("--- DEBUG: ENVIRONMENT CHECK ---")
    print(f"DATABASE_URL found: {os.environ.get('DATABASE_URL') is not None}")
    print("--------------------------------")

_load_env()

from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, send_from_directory

from civil_engineering.job_parser                        import parse_job_description
from civil_engineering.normalization.normalize_cv        import normalize_cv
from civil_engineering.intelligence.builder              import build_intelligence
from civil_engineering.cv_adapter.adapter                import adapt_cv
from civil_engineering.cover_letter.cover_letter_builder import build_cover_letter
from civil_engineering.cv_tailor                         import ai_rewrite_cv, generate_cv_summary
from civil_engineering.cv_pdf                            import generate_cv_pdf
from civil_engineering.cv_reader                         import parse_cv_from_bytes
from civil_engineering.cv_pdf                            import generate_cv_pdf
from civil_engineering.cv_reader                         import parse_cv_from_bytes
from civil_engineering.scoring.job_ranker                import rank_job
from civil_engineering.decision_explainer                import explain_decisions
from civil_engineering.eligibility.job_filter            import is_job_relevant

CV_PATH = os.path.join(ROOT, 'civil_engineering', 'data', 'cv.json')

with open(CV_PATH) as f:
    BASE_CV = normalize_cv(json.load(f))

app = Flask(__name__)

# ── Rate limiter (in-memory, per IP) ─────────────────────────────────────────
_RATE: dict = defaultdict(list)
_RATE_LIMIT  = 20   # max requests
_RATE_WINDOW = 60   # per N seconds

def _check_rate(ip: str) -> bool:
    now = time.time()
    _RATE[ip] = [t for t in _RATE[ip] if now - t < _RATE_WINDOW]
    if len(_RATE[ip]) >= _RATE_LIMIT:
        return False
    _RATE[ip].append(now)
    return True

# ── File validation ───────────────────────────────────────────────────────────
MAX_CV_SIZE_MB = 5
ALLOWED_MIME   = {'application/pdf'}

def _validate_cv_file(file) -> tuple[bool, str]:
    if not file or not file.filename:
        return False, 'No file provided'
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.pdf',):
        return False, f'Only PDF files accepted (got {ext})'
    data = file.read()
    file.seek(0)
    size_mb = len(data) / (1024 * 1024)
    if size_mb > MAX_CV_SIZE_MB:
        return False, f'File too large ({size_mb:.1f}MB). Max {MAX_CV_SIZE_MB}MB'
    if not data.startswith(b'%PDF'):
        return False, 'File does not appear to be a valid PDF'
    return True, 'ok'
# Stable key so sessions survive server restarts during development
_SECRET = os.environ.get('FLASK_SECRET', '')
if not _SECRET:
    import secrets as _sec
    _SECRET = _sec.token_hex(32)   # random per-process key (dev only — set FLASK_SECRET in prod)
app.secret_key = _SECRET
from flask import session

# In-memory CV store — keyed by session id, LRU eviction at 200 sessions.
_SESSION_CVS: dict = {}
_SESSION_TS:  dict = {}
_SESSION_MAX       = 200

def _get_session_cv(sid):
    if not sid: return None
    cv = _SESSION_CVS.get(sid)
    if cv: _SESSION_TS[sid] = time.time()
    return cv

def _set_session_cv(sid, cv):
    _SESSION_CVS[sid] = cv
    _SESSION_TS[sid]  = time.time()
    if len(_SESSION_CVS) > _SESSION_MAX:
        oldest = sorted(_SESSION_TS, key=_SESSION_TS.get)[:20]
        for s in oldest:
            _SESSION_CVS.pop(s, None)
            _SESSION_TS.pop(s, None)


def _persist_cv_to_db(user_id, cv_data_json):
    """Move a guest CV from temporary storage to the permanent user record."""
    try:
        conn = _tracker_db()
        cur = conn.cursor()
        PL = '%s' if USE_POSTGRES else '?'
        
        # Update the cv_data column for the specific user
        query = f"UPDATE users SET cv_data = {PL} WHERE id = {PL}"
        
        cur.execute(query, (cv_data_json, user_id))
        
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"CV PERSISTENCE ERROR: {e}")

def _load_cv_from_db(uid: str):
    """Load CV JSON from DB. Returns dict or None."""
    if not uid:
        return None
    try:
        conn = _tracker_db()
        cur = conn.cursor()
        PL = '%s' if USE_POSTGRES else '?'
        
        # Use the cursor and the dynamic placeholder
        cur.execute(f'SELECT cv_data FROM users WHERE id={PL}', (uid,))
        row = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if row and row['cv_data']:
            # row['cv_data'] works for both SQLite Row and Postgres DictCursor
            import json
            return json.loads(row['cv_data'])
    except Exception as e:
        print(f"CV LOAD ERROR: {e}")
        pass
    return None

# ── Pipeline ──────────────────────────────────────────────────────────────────

def _friendly_seniority(raw: str) -> str:
    """Convert internal seniority codes to user-friendly labels."""
    return {
        'underqualified':          'Below requirements',
        'matched':                 'Good match',
        'tolerated_overqualified': 'Senior — still apply',
        'overqualified':           'Overqualified',
        'unknown':                 'Not specified',
    }.get(raw, raw.replace('_', ' ').title())


def run_pipeline(raw_text: str, cv_override: dict | None = None) -> dict:
    job      = parse_job_description(raw_text)
    job_dict = job.to_dict()

    # Use uploaded CV if available, otherwise fall back to default
    active_cv = cv_override if cv_override else BASE_CV
    is_relevant, reason = is_job_relevant(active_cv, job_dict, raw_text=raw_text)
    if not is_relevant:
        return {'status': 'rejected', 'reason': reason, 'job': {
            'title': job.title, 'salary': job.salary,
        }}

    cv           = copy.deepcopy(active_cv)
    intelligence = build_intelligence(cv, job_dict)
    decisions    = explain_decisions(cv, job_dict, intelligence)
    conf_block   = next((d for d in decisions if d.get('type') == 'confidence_score'), {})
    confidence   = conf_block.get('overall_confidence', 0)
    ranking      = rank_job(confidence)
    adapted_cv   = adapt_cv(cv, job_dict, intelligence)

    tailor       = ai_rewrite_cv(adapted_cv, job_dict, intelligence)
    cv_summary   = tailor.get('summary') or generate_cv_summary(adapted_cv, job_dict)
    provider     = tailor.get('provider', 'rule-based')

    cover_letter = build_cover_letter(
        profile      = active_cv['profile'],
        job          = job_dict,
        intelligence = intelligence,
        cv           = adapted_cv,
        ai_summary   = cv_summary,
    )

    filled  = int(confidence / 5)
    bar_pct = confidence

    return {
        'status':       'ok',
        'job': {
            'title':    job.title or 'Not detected',
            'years':    job.years_required or 'Not specified',
            'projects': ', '.join(job.project_types) or 'Not detected',
            'salary':   job.salary or 'Not specified',
            'location': job.location or 'Not specified',
            'skills':   ', '.join(job.required_skills[:5]) if job.required_skills else '',
            'email':    job.apply_email or '',
            'company':  job.company or '',
        },
        'match': {
            'confidence':  confidence,
            'bar_pct':     bar_pct,
            'rank':        ranking['rank'],
            'action':      ranking['action'],
            'seniority':   _friendly_seniority(intelligence.get('seniority', 'unknown')),
            'alignment':   intelligence.get('project_alignment', {}).get('strength', 'none').title(),
            'risk_flags':  [f.replace('_', ' ') for f in intelligence.get('risk_flags', [])],
        },
        'cv_summary':    cv_summary,
        'provider':      provider.upper(),
        'cover_letter':  cover_letter,
    }

# ── Routes ─────────────────────────────────────────────────────────────────
# WHY A SERVER-SIDE REDIRECT FOR EMAIL?
# Building the Yahoo Mail URL in JS and setting it on an <a> tag works,
# but browsers sometimes block it if the href wasn't set at page load time.
# A server-side /compose route is 100% reliable: the link is always a real
# Flask URL (set at page load as href), clicking it is a normal link click,
# Flask builds the Yahoo URL and returns a redirect. No JS needed at all.────

@app.route('/')
def landing():
    return send_from_directory('static', 'landing.html')


@app.route('/app')
def index():
    profile    = BASE_CV.get('profile', {})
    groq_key   = os.environ.get('GROQ_API_KEY', '')
    cohere_key = os.environ.get('COHERE_API_KEY', '')
    if cohere_key:
        provider_label = 'Cohere AI — FREE'
    elif groq_key:
        provider_label = 'Groq AI — FREE'
    else:
        provider_label = 'Rule-based'
    # First-visit flag: has this browser session uploaded a CV yet?
    has_cv = bool(session.get('cv_id') and _get_session_cv(session.get('cv_id')))
    return render_template_string(HTML_TEMPLATE,
        name=profile.get('name', ''),
        years=profile.get('experience_years', ''),
        provider=provider_label,
        first_visit=('false' if has_cv else 'true'),
    )

@app.route('/test-email')
def test_email():
    """Test page — open at http://localhost:5000/test-email"""
    return render_template_string('''<!DOCTYPE html>
<html>
<body style="font-family:monospace;padding:40px;background:#111;color:#eee;max-width:600px">
<h2 style="color:#c8f060">Email Button Test</h2>
<p style="color:#aaa;margin-bottom:20px">Make sure you are logged into Yahoo Mail first, then click the button.</p>
<a href="https://compose.mail.yahoo.com/?to=victor.f%40rovedana.com&subject=Application+for+Civil+Construction+Engineer&body=Dear+Hiring+Manager%2C%0A%0ATest+email.%0A%0AYours+sincerely%2C+Sikiru"
   target="_blank" rel="noopener noreferrer"
   style="display:inline-block;background:#16200a;border:1px solid #f0a030;color:#f0a030;padding:12px 24px;text-decoration:none;border-radius:3px;font-size:13px">
  ✉ Open Yahoo Mail Compose (test)
</a>
<p style="margin-top:20px;color:#666;font-size:11px">If this works, the main app button will work too — same URL format.</p>
</body></html>''')


@app.route('/compose')
def compose():
    """
    Build the Yahoo Mail compose URL server-side and redirect.
    Called by the email button — query params: to, subject, body.
    Using a redirect means the button href is always a real URL (never '#')
    so no popup blocker can interfere.
    """
    import urllib.parse
    from flask import redirect, request as req
    to      = req.args.get('to', '')
    subject = req.args.get('subject', '')
    body    = req.args.get('body', '')
    yahoo   = (
        'https://compose.mail.yahoo.com/?to='
        + urllib.parse.quote(to)
        + '&subject=' + urllib.parse.quote(subject)
        + '&body='    + urllib.parse.quote(body)
    )
    return redirect(yahoo)


@app.route('/upload-cv', methods=['POST'])
def upload_cv():
    """
    Accept a CV PDF upload, parse it, store in session.
    Returns the extracted profile so the UI can confirm it.
    """
    if 'cv_file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file uploaded'})

    f = request.files['cv_file']
    valid, msg = _validate_cv_file(f)
    if not valid:
        return jsonify({'status': 'error', 'message': msg})

    try:
        pdf_bytes = f.read()
        if len(pdf_bytes) > 5 * 1024 * 1024:  # 5MB limit
            return jsonify({'status': 'error', 'message': 'File too large (max 5MB)'})

        try:
            parsed_cv = parse_cv_from_bytes(pdf_bytes, f.filename)
        except Exception as parse_err:
            err_str = str(parse_err).lower()
            if 'timed out' in err_str or 'timeout' in err_str:
                return jsonify({'status': 'error', 'message': 'CV parsing timed out — please try again. This usually succeeds on the second attempt.'})
            if 'nonetype' in err_str or 'attribute' in err_str:
                return jsonify({'status': 'error', 'message': 'Could not read your CV. Make sure it is a text-based PDF, not a scanned image.'})
            raise

        # Check if CV is civil engineering
        from civil_engineering.cv_reader import detect_cv_industry
        industry = detect_cv_industry(parsed_cv)

        # Store in server-side session store regardless (let user decide)
        from flask import session
        import uuid
        sid = session.get('cv_id')
        if not sid:
            sid = str(uuid.uuid4())
            session['cv_id'] = sid
        _set_session_cv(sid, parsed_cv)
        _log_event('cv_uploaded', {'skills': len(parsed_cv.get('skills', [])), 'exp': len(parsed_cv.get('experience', []))})
        # Persist to DB if user is logged in
        uid = session.get('user_id')
        if uid:
            _persist_cv_to_db(uid, parsed_cv)

        profile = parsed_cv['profile']
        return jsonify({
            'status':    'ok',
            'name':      profile.get('name', ''),
            'title':     profile.get('title', ''),
            'years':     profile.get('experience_years', 0),
            'email':     profile.get('email', ''),
            'skills':    parsed_cv.get('skills', [])[:8],
            'exp_count': len(parsed_cv.get('experience', [])),
            'is_civil':  industry['is_civil'],
            'warning':   industry['warning'],
            'detected':  industry['detected'],
            'session_id': sid,   # JS stores this and sends it back on /process
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/download-cv', methods=['POST'])
def download_cv():
    """Generate and serve a tailored CV PDF for download."""
    import tempfile
    from flask import send_file
    data       = request.get_json()
    cv_summary = (data or {}).get('cv_summary', '')
    job_title  = (data or {}).get('job_title', 'role').replace(' ', '_').replace('/', '_')
    try:
        # Use uploaded CV if available, otherwise fall back to default
        sid        = session.get('cv_id')
        active_cv  = _get_session_cv(sid) if sid else None
        active_cv  = active_cv or BASE_CV
        candidate  = active_cv.get('profile', {}).get('name', 'Candidate').replace(' ', '_')
        tmp_path   = os.path.join(tempfile.gettempdir(), f"cv_{job_title}.pdf")
        generate_cv_pdf(active_cv, tmp_path, cv_summary=cv_summary)
        _log_event('cv_downloaded', {'job_title': job_title})
        return send_file(tmp_path, as_attachment=True,
                         download_name=f"{candidate}_CV_{job_title}.pdf",
                         mimetype='application/pdf')
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/process', methods=['POST'])
def process():
    if not _check_rate(request.remote_addr):
        return jsonify({'status': 'error', 'message': 'Too many requests. Please wait a minute.'})
    data = request.get_json()
    raw_text = (data or {}).get('job_description', '').strip()
    if not raw_text:
        return jsonify({'status': 'error', 'message': 'No job description provided'})
    try:
        from flask import session
        # Try cookie session first, then JS-supplied session_id as fallback
        sid = session.get('cv_id') or (data or {}).get('session_id')
        cv_override = _get_session_cv(sid) if sid else None
        result = run_pipeline(raw_text, cv_override=cv_override)
        _log_event('cv_generated', {'confidence': result.get('confidence', 0), 'rank': result.get('rank', '')})
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e), 'trace': traceback.format_exc()})


@app.route('/scrape-jobs', methods=['POST'])
def scrape_jobs():
    """Fetch live construction industry jobs, optionally filtered by profession."""
    if not _check_rate(request.remote_addr):
        return jsonify({'status': 'error', 'message': 'Too many requests. Please wait.'})
    try:
        from civil_engineering.scraper.job_scraper import fetch_jobs, filter_by_profession
        data          = request.get_json() or {}
        sources       = data.get('sources', ['jobberman', 'myjobmag', 'ngcareers', 'hotng', 'linkedin'])
        max_pages     = min(int(data.get('max_pages', 2)), 3)
        force_refresh = bool(data.get('force_refresh', False))
        profession    = data.get('profession', 'all').strip().lower()
        jobs = fetch_jobs(sources=sources, max_pages=max_pages, force_refresh=force_refresh)
        jobs = filter_by_profession(jobs, profession)
        return jsonify({'status': 'ok', 'jobs': jobs, 'count': len(jobs),
                        'cached': not force_refresh, 'profession': profession})
    except RuntimeError as e:
        # Clear user-facing errors (e.g. Playwright not installed)
        return jsonify({'status': 'error', 'message': str(e), 'install_needed': True})
    except Exception as e:
        app.logger.error(f"Scrape error: {traceback.format_exc()}")
        return jsonify({'status': 'error', 'message': f'Scraping failed: {str(e)}'})



@app.route('/fetch-job-detail', methods=['POST'])
def fetch_job_detail():
    """Fetch full job description from a job listing URL."""
    import re as _re
    try:
        data = request.get_json() or {}
        url  = data.get('url', '').strip()
        if not url or not url.startswith('http'):
            return jsonify({'status': 'error', 'message': 'Invalid URL'})

        import requests as req
        from bs4 import BeautifulSoup

        HDRS = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        # timeout=(connect_secs, read_secs) — fail fast rather than hanging
        TIMEOUT = (6, 10)
        r = None
        for attempt in range(2):   # 1 retry on timeout
            try:
                r = req.get(url, headers=HDRS, timeout=TIMEOUT)
                break
            except req.exceptions.Timeout:
                if attempt == 0:
                    app.logger.warning(f"fetch-job-detail: timeout on attempt 1, retrying — {url}")
                    continue
                app.logger.warning(f"fetch-job-detail: timed out after retry — {url}")
                return jsonify({'status': 'error',
                                'message': 'Job page took too long to load. Please open the job link and paste the description manually.'})
            except req.exceptions.ConnectionError as ce:
                app.logger.warning(f"fetch-job-detail: connection error — {url}: {ce}")
                return jsonify({'status': 'error',
                                'message': 'Could not connect to the job page. Check your internet connection.'})

        if r is None or r.status_code != 200:
            code = r.status_code if r is not None else '—'
            return jsonify({'status': 'error', 'message': f'Could not fetch job page (HTTP {code})'})

        soup = BeautifulSoup(r.text, 'html.parser')

        # ── Junk phrases to cut off extraction at ─────────────────────────────
        JUNK = [
            'important safety tips', 'do not make any payment',
            'jobberman customer support', 'report job', 'stay productive',
            'stop receiving', 'pause all job alerts', 'lorem ipsum',
            'join our newsletter', 'latest job listings', 'career insights',
            'delivered straight to your inbox', 'we care about the protection',
            'get the latest updates', 'this action will pause',
        ]

        def clean_text(raw):
            lines = []
            for line in raw.splitlines():
                line = line.strip()
                if not line or len(line) < 4:
                    continue
                if any(j in line.lower() for j in JUNK):
                    break   # everything after first junk line is footer noise
                lines.append(line)
            return '\n'.join(lines)

        # ── Helper: extract apply email from page ────────────────────────────
        def extract_apply_email(soup_obj, nd_json=None):
            """Return (email_or_None, apply_method) where method is 'email' or 'platform'."""
            import re as _r
            EMAIL_PAT = _r.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')

            # 1. Next.js JSON fields
            if nd_json:
                def _find_email(obj, depth=0):
                    if depth > 8 or not isinstance(obj, dict): return ''
                    for key in ('apply_email', 'applyEmail', 'email', 'contact_email',
                                'applicationEmail', 'recruiter_email'):
                        val = obj.get(key, '')
                        if isinstance(val, str) and EMAIL_PAT.match(val):
                            return val
                    for v in obj.values():
                        if isinstance(v, dict):
                            found = _find_email(v, depth + 1)
                            if found: return found
                    return ''
                em = _find_email(nd_json.get('props', {}).get('pageProps', {}))
                if em: return em, 'email'

            # 2. mailto: links on the page
            for a in soup_obj.find_all('a', href=True):
                href = a['href']
                if href.startswith('mailto:'):
                    em = href[7:].split('?')[0].strip()
                    if em and EMAIL_PAT.match(em):
                        return em, 'email'

            # 3. Raw email pattern in apply/contact sections
            for el in soup_obj.find_all(class_=_r.compile(r'apply|contact|email', _r.I)):
                txt = el.get_text()
                found = EMAIL_PAT.findall(txt)
                # Exclude Jobberman's own domain emails
                real = [e for e in found if not e.endswith('@jobberman.com')
                        and not e.endswith('@myjobmag.com')]
                if real: return real[0], 'email'

            # 4. Detect "Easy Apply" or platform-only apply
            for el in soup_obj.find_all(class_=_r.compile(r'easy.?apply|apply.?btn|apply.?now', _r.I)):
                return None, 'platform'
            if soup_obj.find(string=_r.compile(r'Easy Apply', _r.I)):
                return None, 'platform'

            return None, 'platform'   # default: assume platform apply

        # Strategy 1: Next.js __NEXT_DATA__ JSON (Jobberman) ─────────────────
        nd_json = None
        script = soup.find('script', id='__NEXT_DATA__')
        if script:
            import json as _json
            try:
                nd_json = _json.loads(script.string)

                def _find_desc(obj, depth=0):
                    if depth > 8 or not isinstance(obj, dict):
                        return ''
                    for key in ('description', 'body', 'summary', 'details',
                                'content', 'jobDescription', 'job_description'):
                        val = obj.get(key, '')
                        if isinstance(val, str) and len(val) > 150:
                            return val
                    for v in obj.values():
                        if isinstance(v, dict):
                            found = _find_desc(v, depth + 1)
                            if found:
                                return found
                    return ''

                props = nd_json.get('props', {}).get('pageProps', {})
                raw_desc = _find_desc(props)
                if raw_desc:
                    from bs4 import BeautifulSoup as BS
                    text = BS(raw_desc, 'html.parser').get_text(separator='\n')
                    text = clean_text(text)
                    apply_email, apply_method = extract_apply_email(soup, nd_json)
                    if len(text) > 100:
                        app.logger.info(f"fetch-job-detail: {len(text)} chars via Next.js JSON | email={apply_email}")
                        return jsonify({'status': 'ok', 'description': text[:4000],
                                        'apply_email': apply_email, 'apply_method': apply_method})
            except Exception as e:
                app.logger.debug(f"Next.js parse error: {e}")

        # Strategy 2: Remove noisy elements, then find description container ──
        for tag in soup.find_all(['nav', 'footer', 'header', 'aside',
                                    'script', 'style', 'noscript']):
            tag.decompose()
        for tag in soup.find_all(class_=_re.compile(
                r'newsletter|safety|tip|alert|banner|cookie|modal|sidebar|'
                r'related|similar|share|social', _re.I)):
            tag.decompose()

        desc_el = (
            soup.find(attrs={'itemprop': 'description'}) or
            soup.find(class_=_re.compile(
                r'job[-_]?desc|job[-_]?body|job[-_]?detail|listing[-_]?desc', _re.I)) or
            soup.find(id=_re.compile(r'job[-_]?desc|job[-_]?body|job[-_]?detail', _re.I)) or
            soup.find('section', class_=_re.compile(
                r'desc|detail|require|responsibilit', _re.I))
        )
        apply_email, apply_method = extract_apply_email(soup, nd_json)

        if desc_el:
            text = clean_text(desc_el.get_text(separator='\n'))
            if len(text) > 100:
                app.logger.info(f"fetch-job-detail: {len(text)} chars via HTML element | email={apply_email}")
                return jsonify({'status': 'ok', 'description': text[:4000],
                                'apply_email': apply_email, 'apply_method': apply_method})

        # Strategy 3: Walk main/article, stop at first junk line ─────────────
        main = (soup.find('main') or soup.find('article') or
                soup.find(id=_re.compile(r'main|content', _re.I)))
        if main:
            parts = []
            for el in main.find_all(['h1', 'h2', 'h3', 'p', 'li']):
                txt = el.get_text().strip()
                if not txt or len(txt) < 4:
                    continue
                if any(j in txt.lower() for j in JUNK):
                    break
                parts.append(txt)
            text = '\n'.join(parts)
            if len(text) > 100:
                app.logger.info(f"fetch-job-detail: {len(text)} chars via main fallback | email={apply_email}")
                return jsonify({'status': 'ok', 'description': text[:4000],
                                'apply_email': apply_email, 'apply_method': apply_method})

        # Strategy 4: log exactly what we got so we can debug
        app.logger.warning(f"fetch-job-detail: could not extract from {url}")
        app.logger.warning(f"  Page length: {len(r.text)}, has Next.js: {bool(soup.find('script', id='__NEXT_DATA__'))}")
        app.logger.warning(f"  First 500 chars: {r.text[:500]}")
        return jsonify({'status': 'error', 'message': 'Could not extract job description — try pasting it manually from the job page', 'url': url})

    except Exception as e:
        app.logger.error(f"fetch-job-detail exception: {e}")
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/send-application', methods=['POST'])
def send_application():
    """Send tailored CV + cover letter by email via SMTP."""
    import smtplib, tempfile
    from email.mime.multipart import MIMEMultipart
    from email.mime.text      import MIMEText
    from email.mime.base      import MIMEBase
    from email                import encoders

    data         = request.get_json() or {}
    to_email     = data.get('to_email', '').strip()
    subject      = data.get('subject', '').strip()
    body         = data.get('body', '').strip()
    cv_summary   = data.get('cv_summary', '')
    job_title    = data.get('job_title', 'role').replace(' ', '_').replace('/', '_')

    if not to_email:
        return jsonify({'status': 'error', 'message': 'No recipient email address'})

    # Sender credentials from env
    sender_email = os.environ.get('SMTP_EMAIL', '').strip()
    sender_pass  = os.environ.get('SMTP_PASSWORD', '').strip()
    smtp_host    = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    smtp_port    = int(os.environ.get('SMTP_PORT', '587'))

    if not sender_email or not sender_pass:
        return jsonify({
            'status': 'error',
            'message': 'Email not configured. Add SMTP_EMAIL and SMTP_PASSWORD to your .env file.',
            'setup_needed': True
        })

    try:
        # Generate CV PDF
        sid       = session.get('cv_id')
        active_cv = _get_session_cv(sid) if sid else None
        active_cv = active_cv or BASE_CV
        candidate = active_cv.get('profile', {}).get('name', 'Candidate')
        tmp_path  = os.path.join(tempfile.gettempdir(), f"cv_{job_title}.pdf")
        generate_cv_pdf(active_cv, tmp_path, cv_summary=cv_summary)

        # Build email
        msg = MIMEMultipart()
        msg['From']    = f"{candidate} <{sender_email}>"
        msg['To']      = to_email
        msg['Subject'] = subject or f"Application for {job_title.replace('_', ' ')}"
        msg.attach(MIMEText(body or f"Dear Hiring Manager,\n\nPlease find my CV attached.\n\nYours sincerely,\n{candidate}", 'plain'))

        # Attach CV PDF
        with open(tmp_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
        encoders.encode_base64(part)
        cv_filename = f"{candidate.replace(' ', '_')}_CV_{job_title}.pdf"
        part.add_header('Content-Disposition', f'attachment; filename="{cv_filename}"')
        msg.attach(part)

        # Send
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_pass)
            server.send_message(msg)

        app.logger.info(f"send-application: sent to {to_email} from {sender_email}")
        return jsonify({'status': 'ok', 'message': f'Application sent to {to_email}'})

    except smtplib.SMTPAuthenticationError:
        return jsonify({'status': 'error', 'message': 'Email login failed. Check your SMTP_EMAIL and SMTP_PASSWORD in .env'})
    except Exception as e:
        app.logger.error(f"send-application error: {e}")
        return jsonify({'status': 'error', 'message': str(e)})




# ── Batch Apply ────────────────────────────────────────────────────────────────

@app.route('/batch-preview', methods=['POST'])
def batch_preview():
    """
    Scrape jobs, score each against CV, return ranked list.
    Uses job title + snippet for fast scoring — no full JD fetch needed.
    Pipeline fields fall back to raw scraper data for title/company/location.
    """
    if not _check_rate(request.remote_addr):
        return jsonify({'status': 'error', 'message': 'Too many requests. Please wait.'})

    data           = request.get_json() or {}
    min_confidence = int(data.get('min_confidence', 55))
    email_only     = bool(data.get('email_only', False))

    try:
        from civil_engineering.scraper.job_scraper import fetch_jobs
        jobs = fetch_jobs(
            sources=['jobberman', 'myjobmag', 'ngcareers', 'hotng', 'linkedin'],
            max_pages=2, force_refresh=False
        )
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Scraping failed: {e}'})

    sid       = session.get('cv_id')
    active_cv = _get_session_cv(sid) if sid else None
    active_cv = active_cv or BASE_CV

    results   = []
    skipped   = 0

    for job in jobs:
        try:
            # ── Lightweight scoring only — no AI rewrite, no cover letter ──
            # Full run_pipeline makes 4-5 AI calls per job. With 30+ jobs that
            # causes timeouts. We only need: parse → relevance check → confidence.
            from civil_engineering.job_parser                          import parse_job_description
            from civil_engineering.intelligence.builder                import build_intelligence
            from civil_engineering.decision_explainer.decision_explainer import explain_decisions
            from civil_engineering.eligibility.job_filter              import is_job_relevant
            from civil_engineering.scoring.job_ranker                  import rank_job

            snippet_text = ' '.join(filter(None, [
                job.get('title', ''),
                job.get('snippet', ''),
                job.get('location', ''),
                job.get('salary', ''),
            ]))

            parsed = parse_job_description(snippet_text)
            job_dict = parsed.to_dict()

            relevant, reason = is_job_relevant(active_cv, job_dict, raw_text=snippet_text)
            if not relevant:
                skipped += 1
                continue

            intelligence = build_intelligence(active_cv, job_dict)
            decisions    = explain_decisions(active_cv, job_dict, intelligence)
            conf_block   = next((d for d in decisions if d.get('type') == 'confidence_score'), {})
            confidence   = conf_block.get('overall_confidence', 0)

        except Exception as e:
            app.logger.debug(f'Batch score error: {e}')
            skipped += 1
            continue

        if confidence < min_confidence:
            skipped += 1
            continue

        apply_email = job.get('email', '')
        if email_only and not apply_email:
            skipped += 1
            continue

        ranking = rank_job(confidence)
        results.append({
            'title':        job.get('title', 'Unknown'),
            'company':      job.get('company', ''),
            'location':     job.get('location', ''),
            'salary':       job.get('salary', ''),
            'source':       job.get('source', ''),
            'url':          job.get('url', ''),
            'apply_email':  apply_email,
            'confidence':   confidence,
            'rank':         ranking.get('rank', ''),
            'can_email':    bool(apply_email),
            # cover_letter left empty — generated on demand when user clicks Send
            'cover_letter': '',
            'cv_summary':   '',
        })

    results.sort(key=lambda x: x['confidence'], reverse=True)

    return jsonify({
        'status':   'ok',
        'results':  results,
        'total':    len(results),
        'skipped':  skipped,
    })


@app.route('/batch-send', methods=['POST'])
def batch_send():
    """Send tailored CVs to a list of jobs (email-apply only)."""
    import smtplib, tempfile, time as _time
    from email.mime.multipart import MIMEMultipart
    from email.mime.text      import MIMEText
    from email.mime.base      import MIMEBase
    from email                import encoders

    data = request.get_json() or {}
    jobs = data.get('jobs', [])   # list of {title, company, apply_email, cv_summary, cover_letter, url}

    if not jobs:
        return jsonify({'status': 'error', 'message': 'No jobs provided'})

    sender_email = os.environ.get('SMTP_EMAIL', '').strip()
    sender_pass  = os.environ.get('SMTP_PASSWORD', '').strip()
    smtp_host    = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    smtp_port    = int(os.environ.get('SMTP_PORT', '587'))

    if not sender_email or not sender_pass:
        return jsonify({
            'status': 'error',
            'message': 'Email not configured. Add SMTP_EMAIL and SMTP_PASSWORD.',
            'setup_needed': True
        })

    sid       = session.get('cv_id')
    active_cv = _get_session_cv(sid) if sid else None
    active_cv = active_cv or BASE_CV
    candidate = active_cv.get('profile', {}).get('name', 'Candidate')

    sent    = []
    failed  = []

    try:
        smtp = smtplib.SMTP(smtp_host, smtp_port)
        smtp.starttls()
        smtp.login(sender_email, sender_pass)
    except smtplib.SMTPAuthenticationError:
        return jsonify({'status': 'error', 'message': 'Email login failed. Check SMTP_EMAIL and SMTP_PASSWORD.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Could not connect to email server: {e}'})

    for job in jobs:
        to_email   = (job.get('apply_email') or '').strip()
        title      = job.get('title', 'the advertised role')
        cv_summary = job.get('cv_summary', '')
        body       = job.get('cover_letter', '')
        job_slug   = title.replace(' ', '_').replace('/', '_')[:40]

        if not to_email:
            failed.append({'title': title, 'reason': 'No email address'})
            continue

        try:
            # Generate tailored CV PDF
            tmp_path = os.path.join(tempfile.gettempdir(), f'cv_batch_{job_slug}.pdf')
            generate_cv_pdf(active_cv, tmp_path, cv_summary=cv_summary)

            msg = MIMEMultipart()
            msg['From']    = f"{candidate} <{sender_email}>"
            msg['To']      = to_email
            msg['Subject'] = f"Application for {title}"
            msg.attach(MIMEText(body or f"Dear Hiring Manager,\n\nPlease find my CV attached.\n\nYours sincerely,\n{candidate}", 'plain'))

            with open(tmp_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition',
                            f'attachment; filename="{candidate.replace(" ","_")}_CV_{job_slug}.pdf"')
            msg.attach(part)

            smtp.send_message(msg)
            sent.append({'title': title, 'to': to_email})
            app.logger.info(f"batch-send: sent to {to_email} for {title}")

            # Small delay to avoid spam filters
            _time.sleep(2)

        except Exception as e:
            failed.append({'title': title, 'reason': str(e)})
            app.logger.error(f"batch-send error for {title}: {e}")

    smtp.quit()

    # Log all sent jobs to tracker
    for s in sent:
        try:
            conn = _tracker_db()
            conn.execute(
                '''INSERT INTO applications (title, company, location, salary, url, platform, method, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (s['title'],
                 next((j.get('company','') for j in jobs if j.get('title') == s['title']), ''),
                 next((j.get('location','') for j in jobs if j.get('title') == s['title']), ''),
                 next((j.get('salary','') for j in jobs if j.get('title') == s['title']), ''),
                 next((j.get('url','') for j in jobs if j.get('title') == s['title']), ''),
                 'Batch Apply', 'Email', 'Applied')
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    return jsonify({
        'status': 'ok',
        'sent':   sent,
        'failed': failed,
        'total_sent': len(sent),
    })

# ── Application Tracker ────────────────────────────────────────────────────────

# def _tracker_db():
#     """Return a sqlite3 connection to the applications tracker DB."""
#     import sqlite3
#     db_path = os.path.join(DATA_DIR, 'applications.db')
#     conn = sqlite3.connect(db_path)
#     conn.row_factory = sqlite3.Row
DATABASE_URL = os.environ.get('DATABASE_URL')
USE_POSTGRES = bool(DATABASE_URL)

def _tracker_db():
    if USE_POSTGRES:
        import psycopg2, psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL, sslmode='require', cursor_factory=psycopg2.extras.DictCursor)
        _setup_postgres(conn)
        return conn
    else:
        import sqlite3
        db_path = os.path.join(DATA_DIR, 'applications.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute('''CREATE TABLE IF NOT EXISTS applications (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   TEXT DEFAULT '',
            title     TEXT NOT NULL,
            company   TEXT,
            location  TEXT,
            salary    TEXT,
            url       TEXT,
            platform  TEXT,
            method    TEXT,
            status    TEXT DEFAULT 'Applied',
            notes     TEXT DEFAULT '',
            applied_at TEXT DEFAULT (datetime('now', 'localtime'))
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id            TEXT PRIMARY KEY,
            email         TEXT UNIQUE NOT NULL,
            name          TEXT DEFAULT '',
            password_hash TEXT DEFAULT '',
            cv_data       TEXT DEFAULT '',
            created_at    TEXT DEFAULT (datetime('now', 'localtime')),
            last_seen     TEXT DEFAULT (datetime('now', 'localtime'))
        )''')
        # Migrate: rebuild users table if it was created without 'id' column
        # (this happens when Render's persistent DB was created by an older deploy)
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
            if 'id' not in cols:
                conn.execute('''CREATE TABLE IF NOT EXISTS users_new (
                    id            TEXT PRIMARY KEY,
                    email         TEXT UNIQUE NOT NULL,
                    name          TEXT DEFAULT '',
                    password_hash TEXT DEFAULT '',
                    cv_data       TEXT DEFAULT '',
                    created_at    TEXT DEFAULT (datetime('now', 'localtime')),
                    last_seen     TEXT DEFAULT (datetime('now', 'localtime'))
                )''')
                # Copy whatever columns exist in old table
                old_cols = set(cols) & {'email', 'name', 'password_hash', 'cv_data', 'created_at', 'last_seen'}
                col_list = ', '.join(old_cols)
                conn.execute(f'INSERT OR IGNORE INTO users_new ({col_list}) SELECT {col_list} FROM users')
                conn.execute('DROP TABLE users')
                conn.execute('ALTER TABLE users_new RENAME TO users')
                conn.commit()
        except Exception:
            pass
        # Migrate: add new columns to users if upgrading old DB
        for _col, _def in [('password_hash', 'TEXT DEFAULT ""'), ('cv_data', 'TEXT DEFAULT ""')]:
            try:
                conn.execute(f'ALTER TABLE users ADD COLUMN {_col} {_def}')
                conn.commit()
            except Exception:
                pass
        # Migrate: add user_id to applications if missing (old DB without it)
        for _col, _def in [('user_id', 'TEXT DEFAULT ""'), ('notes', 'TEXT DEFAULT ""')]:
            try:
                conn.execute(f'ALTER TABLE applications ADD COLUMN {_col} {_def}')
                conn.commit()
            except Exception:
                pass
        conn.execute('''CREATE TABLE IF NOT EXISTS events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    TEXT DEFAULT '',
            session_id TEXT DEFAULT '',
            event      TEXT NOT NULL,
            meta       TEXT DEFAULT '{}',
            ip         TEXT DEFAULT '',
            ua         TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS feedback (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    TEXT DEFAULT '',
            session_id TEXT DEFAULT '',
            rating     INTEGER NOT NULL,
            message    TEXT DEFAULT '',
            context    TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )''')
        conn.commit()
        return conn

def _setup_postgres(conn):
    """Run Postgres-specific table creation."""
    cur = conn.cursor()
    # Note: 'SERIAL' is the Postgres version of 'AUTOINCREMENT'
    try:
        cur.execute('''CREATE TABLE IF NOT EXISTS applications (
            id          SERIAL PRIMARY KEY,
            user_id     TEXT DEFAULT '',
            title       TEXT NOT NULL,
            company     TEXT,
            location    TEXT,
            salary      TEXT,
            url         TEXT,
            platform    TEXT,
            method      TEXT,
            status      TEXT DEFAULT 'Applied',
            notes       TEXT DEFAULT '',
            applied_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        cur.execute('''CREATE TABLE IF NOT EXISTS users (
            id            TEXT PRIMARY KEY,
            email         TEXT UNIQUE NOT NULL,
            name          TEXT DEFAULT '',
            password_hash TEXT DEFAULT '',
            cv_data       TEXT DEFAULT '',
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Add feedback and events for Postgres too
        cur.execute('''CREATE TABLE IF NOT EXISTS feedback (
            id SERIAL PRIMARY KEY, 
            user_id TEXT, rating INTEGER, message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        conn.commit()
    finally:
        cur.close()

@app.route('/tracker/add', methods=['POST'])
def tracker_add():
    """Log a job application to the tracker."""
    data    = request.get_json() or {}
    title   = data.get('title', '').strip()
    if not title:
        return jsonify({'status': 'error', 'message': 'Job title required'})
    try:
        conn = _tracker_db()
        cur = conn.cursor() # Create the worker (cursor)

        placeholder = '%s' if USE_POSTGRES else '?'

        # Check if the user is logged in and use user_id, otherwise fall back to cv_id or 'anonymous'
        uid = session.get('user_id') or session.get('cv_id') or 'anonymous'
        query = f'''INSERT INTO applications 
               (title, company, location, salary, url, platform, method, status, notes, user_id) 
               VALUES ({", ".join([placeholder]*10)})'''
        cur.execute(query, (
        title, data.get('company', ''), data.get('location', ''), 
        data.get('salary', ''), data.get('url', ''), data.get('platform', ''), 
        data.get('method', ''), data.get('status', 'Applied'), data.get('notes', ''), 
        uid
    ))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/tracker/list', methods=['GET'])
def tracker_list():
    """Return all tracked applications as JSON."""
    try:
        conn = _tracker_db()
        cur = conn.cursor() 

        # 1. Use the placeholder variable!
        PL = '%s' if USE_POSTGRES else '?'
        
        uid = session.get('user_id')
        sid = session.get('cv_id', '')

        if uid:
            # 2. Split execute and fetchall
            query = f'SELECT * FROM applications WHERE user_id={PL} OR (user_id={PL} AND user_id != {PL}) ORDER BY applied_at DESC'
            cur.execute(query, (uid, sid, uid))
            rows = cur.fetchall()
        else:
            # 3. Handle 'anonymous' logic carefully
            query = f'SELECT * FROM applications WHERE user_id={PL} OR user_id=\'anonymous\' ORDER BY applied_at DESC'
            cur.execute(query, (sid,))
            rows = cur.fetchall()

        # 4. Conversion to Dictionary
        # SQLite's Row and Postgres's DictCursor both support dict() conversion differently
        result = []
        for r in rows:
            result.append(dict(r))

        cur.close()
        conn.close()
        return jsonify(result)
        
    except Exception as e:
        print(f"TRACKER LIST ERROR: {traceback.format_exc()}")
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/tracker/update', methods=['POST'])
def tracker_update():
    """Update status or notes on an application."""
    data = request.get_json() or {}
    app_id = data.get('id')
    field  = data.get('field', 'status')
    val    = data.get('value', '')
    
    if not app_id:
        return jsonify({'status': 'error', 'message': 'ID required'})
    if field not in ('status', 'notes'):
        return jsonify({'status': 'error', 'message': 'Invalid field'})

    try:
        conn = _tracker_db()
        cur  = conn.cursor()
        PL   = '%s' if USE_POSTGRES else '?'

        uid = session.get('user_id')
        sid = session.get('cv_id', '')

        # Simplified query: check if the record belongs to current user or is anonymous
        query = f'''
            UPDATE applications 
            SET {field} = {PL} 
            WHERE id = {PL} 
              AND (user_id = {PL} OR user_id = {PL} OR user_id = '' OR user_id = 'anonymous')
        '''
        
        # Match the 4 placeholders exactly:
        cur.execute(query, (val, app_id, uid, sid))
        
        conn.commit()
        cur.close() # Always close cursor
        conn.close()
        return jsonify({'status': 'ok'})
    except Exception as e:
        print(f"UPDATE ERROR: {traceback.format_exc()}") # Log to Render console
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/tracker/delete', methods=['POST'])
def tracker_delete():
    """Delete an application from the tracker."""
    data   = request.get_json() or {}
    app_id = data.get('id')
    
    if not app_id:
        return jsonify({'status': 'error', 'message': 'ID required'})
        
    try:
        conn = _tracker_db()
        cur = conn.cursor()
        PL = '%s' if USE_POSTGRES else '?'
        
        # Get both possible identifiers
        uid = session.get('user_id')
        sid = session.get('cv_id', '')
        
        # 3 Placeholders = 3 Values in the tuple
        query = f'''
            DELETE FROM applications 
            WHERE id = {PL} 
              AND (user_id = {PL} OR user_id = {PL} OR user_id = '' OR user_id = 'anonymous')
        '''
        
        cur.execute(query, (app_id, uid, sid))
        
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'status': 'ok'})
    except Exception as e:
        # Adding a print here helps you debug in the Render logs
        print(f"DELETE ERROR: {e}") 
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/cv-data', methods=['GET'])
def cv_data():
    """Return the active CV as JSON for the editor."""
    sid       = session.get('cv_id')
    active_cv = _get_session_cv(sid) if sid else None
    active_cv = active_cv or BASE_CV
    return jsonify({
        'status': 'ok',
        'profile':    active_cv.get('profile', {}),
        'experience': active_cv.get('experience', []),
        'education':  active_cv.get('education', []),
        'skills':     active_cv.get('skills', []),
    })


@app.route('/cv-save', methods=['POST'])
def cv_save():
    """Save edited CV sections back to the session."""
    data = request.get_json() or {}
    sid  = session.get('cv_id')
    if not sid:
        import uuid
        sid = str(uuid.uuid4())
        session['cv_id'] = sid

    active_cv = _get_session_cv(sid) if sid else None
    active_cv = copy.deepcopy(active_cv or BASE_CV)

    # Update whichever sections were sent
    if 'profile' in data:
        active_cv['profile'].update(data['profile'])
    if 'experience' in data:
        active_cv['experience'] = data['experience']
    if 'education' in data:
        active_cv['education'] = data['education']
    if 'skills' in data:
        active_cv['skills'] = data['skills']

    _set_session_cv(sid, active_cv)
    # Persist to DB if logged in
    uid = session.get('user_id')
    if uid:
        _persist_cv_to_db(uid, active_cv)
    return jsonify({'status': 'ok'})


@app.route('/session-check')
def session_check():
    """Tell the frontend whether this visitor has uploaded a CV."""
    sid      = session.get('cv_id')
    has_cv   = bool(sid and _get_session_cv(sid))
    profile  = {}
    if has_cv:
        cv      = _get_session_cv(sid)
        profile = cv.get('profile', {})
    return jsonify({
        'has_cv':  has_cv,
        'name':    profile.get('name', ''),
        'years':   profile.get('experience_years', 0),
    })


@app.route('/account/identify', methods=['POST'])
def account_identify():
    """Associate current session with an email (soft login — no password)."""
    import sqlite3, uuid, re as _re
    data  = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    PL = '%s' if USE_POSTGRES else '?'
    if not email or not _re.match(r'[^@]+@[^@]+\.[^@]+', email):
        return jsonify({'status': 'error', 'message': 'Valid email required'})
    name = data.get('name', '').strip()
    try:
        conn = _tracker_db()
        cur = conn.cursor()
        # Upsert user
        uid = str(uuid.uuid5(uuid.NAMESPACE_URL, email))
        query = f'''INSERT INTO users (id, email, name) VALUES ({PL}, {PL}, {PL})
                    ON CONFLICT(email) DO UPDATE SET last_seen=datetime('now','localtime'),
                    name=CASE WHEN excluded.name != '' THEN excluded.name ELSE name END'''
        cur.execute(query, (uid, email, name))
        conn.commit()
        # Store in Flask session
        session['user_id']    = uid
        session['user_email'] = email
        # Migrate any anonymous applications to this user
        sid = session.get('cv_id', '')
        query = f'UPDATE applications SET user_id={PL} WHERE user_id={PL} OR user_id={PL}'
        cur.execute(query, (uid, uid, sid))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'status': 'ok', 'user_id': uid, 'email': email})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/account/me', methods=['GET'])
def account_me():
    """Return current user info."""
    uid   = session.get('user_id')
    email = session.get('user_email', '')
    sid   = session.get('cv_id')
    has_cv = bool(sid and _get_session_cv(sid))
    return jsonify({
        'logged_in': bool(uid),
        'email':     email,
        'user_id':   uid or '',
        'has_cv':    has_cv,
    })


# ── Analytics ──────────────────────────────────────────────────────────────────

def _log_event(event: str, meta: dict = None, uid: str = None):
    """Fire-and-forget event log. Never raises."""
    PL = '%s' if USE_POSTGRES else '?'
    try:
        from flask import has_request_context, request as _req
        conn = _tracker_db()
        cur = conn.cursor()
        sid  = session.get('cv_id', '') if has_request_context() else ''
        uid  = uid or (session.get('user_id', '') if has_request_context() else '')
        ip   = _req.remote_addr if has_request_context() else ''
        ua   = _req.headers.get('User-Agent', '')[:200] if has_request_context() else ''
        query = f'''INSERT INTO events (user_id, session_id, event, meta, ip, ua) 
                    VALUES ({PL}, {PL}, {PL}, {PL}, {PL}, {PL})'''
        cur.execute(query, (uid, sid, event, json.dumps(meta or {}), ip, ua))
        conn.commit()
        cur.close()
        conn.commit()
        conn.close()
    except Exception:
        pass


@app.route('/track', methods=['POST'])
def track():
    """Client-side event tracking."""
    data  = request.get_json() or {}
    event = data.get('event', '').strip()[:80]
    meta  = data.get('meta', {})
    if not event:
        return jsonify({'status': 'error'})
    _log_event(event, meta)
    return jsonify({'status': 'ok'})


@app.route('/feedback', methods=['POST'])
def submit_feedback():
    """Store a thumbs-up/down + optional message after CV download."""
    data    = request.get_json() or {}
    rating  = data.get('rating')   # 1 = thumbs up, 0 = thumbs down
    message = data.get('message', '').strip()[:500]
    context = data.get('context', '').strip()[:200]
    
    if rating not in (0, 1):
        return jsonify({'status': 'error', 'message': 'rating must be 0 or 1'})
    try:
        conn = _tracker_db()
        cur = conn.cursor()
        PL = '%s' if USE_POSTGRES else '?'
        uid  = session.get('user_id')
        sid  = session.get('cv_id')
        query = f'INSERT INTO feedback (user_id, session_id, rating, message, context) VALUES ({PL}, {PL}, {PL}, {PL}, {PL})'
        cur.execute(query, (uid, sid, rating, message, context))
        
        conn.commit()
        cur.close()
        conn.close()
        _log_event('feedback_submitted', {'rating': rating})
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


# ── Auth ───────────────────────────────────────────────────────────────────────

@app.route('/auth/register', methods=['POST'])
def auth_register():
    """Register with email + password."""
    import hashlib, re as _re, uuid
    data     = request.get_json() or {}
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()
    name     = data.get('name', '').strip()

    if not email or not _re.match(r'[^@]+@[^@]+\.[^@]+', email):
        return jsonify({'status': 'error', 'message': 'Valid email required'})
    if len(password) < 8:
        return jsonify({'status': 'error', 'message': 'Password must be at least 8 characters'})

    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    uid     = str(uuid.uuid5(uuid.NAMESPACE_URL, email))

    try:
        conn = _tracker_db()
        cur = conn.cursor()
        PL = '%s' if USE_POSTGRES else '?'

        # 1. Check for existing user
        query_check = f"SELECT id, password_hash FROM users WHERE email={PL}"
        cur.execute(query_check, (email,))
        existing = cur.fetchone()

        if existing:
            # Note: with DictCursor/Row, we can access by key 'password_hash'
            if existing['password_hash']:
                cur.close()
                conn.close()
                return jsonify({'status': 'error', 'message': 'Email already registered. Please log in.'})
            
            # Upgrade soft-login account
            query_upd = f'UPDATE users SET password_hash={PL}, name=CASE WHEN {PL} != "" THEN {PL} ELSE name END WHERE email={PL}'
            cur.execute(query_upd, (pw_hash, name, name, email))
        else:
            # Create new user
            query_ins = f'INSERT INTO users (id, email, name, password_hash) VALUES ({PL}, {PL}, {PL}, {PL})'
            cur.execute(query_ins, (uid, email, name, pw_hash))
        
        conn.commit()

        # 2. Migrate session applications to the new user ID
        sid = session.get('cv_id', '')
        query_mig = f'UPDATE applications SET user_id={PL} WHERE user_id={PL} OR user_id={PL}'
        cur.execute(query_mig, (uid, uid, sid))
        
        conn.commit()
        cur.close()
        conn.close()

        # Update Session
        session['user_id']    = uid
        session['user_email'] = email
        session['user_name']  = name

        # 3. Handle CV persistence (Ensure these helper functions are also updated!)
        sid_cv = session.get('cv_id')
        existing_cv = _get_session_cv(sid_cv) if sid_cv else None
        if existing_cv:
            _persist_cv_to_db(uid, existing_cv)

        _log_event('register', {'email': email})
        
        return jsonify({'status': 'ok', 'user_id': uid, 'email': email, 'name': name})
        
    except Exception as e:
        import traceback
        print(f"REGISTRATION ERROR: {traceback.format_exc()}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/auth/login', methods=['POST'])
def auth_login():
    """Login with email + password."""
    import hashlib
    data     = request.get_json() or {}
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()

    if not email or not password:
        return jsonify({'status': 'error', 'message': 'Email and password required'})

    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    try:
        conn = _tracker_db()
        cur = conn.cursor()
        PL = '%s' if USE_POSTGRES else '?'
        querry = f'SELECT id, email, name, password_hash FROM users WHERE email={PL}'
        cur.execute(querry, (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if not user:
            return jsonify({'status': 'error', 'message': 'No account found for that email'})
        if not user['password_hash']:
            return jsonify({'status': 'error', 'message': 'Account has no password set. Use "forgot password" or register again.'})
        if user['password_hash'] != pw_hash:
            return jsonify({'status': 'error', 'message': 'Incorrect password'})
        session['user_id']    = user['id']
        session['user_email'] = user['email']
        session['user_name']  = user['name']
        # Restore saved CV into memory session
        saved_cv = _load_cv_from_db(user['id'])
        if saved_cv:
            sid = session.get('cv_id')
            if not sid:
                import uuid as _uuid
                sid = str(_uuid.uuid4())
                session['cv_id'] = sid
            _set_session_cv(sid, saved_cv)
        _log_event('login', {'email': email}, uid=user['id'])
        return jsonify({'status': 'ok', 'user_id': user['id'],
                        'email': user['email'], 'name': user['name'],
                        'has_cv': bool(saved_cv)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/auth/logout', methods=['POST'])
def auth_logout():
    _log_event('logout')
    session.pop('user_id', None)
    session.pop('user_email', None)
    session.pop('user_name', None)
    return jsonify({'status': 'ok'})


# ── Admin Dashboard ────────────────────────────────────────────────────────────

@app.route('/admin/stats', methods=['GET'])
def admin_stats():
    """Usage analytics — protected by ADMIN_KEY env var."""
    key = request.args.get('key', '')
    admin_key = os.environ.get('ADMIN_KEY', '')
    if not admin_key or key != admin_key:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    try:
        conn = _tracker_db()
        cur = conn.cursor()
        
        stats = {}

        # 1. Total counts
        # Postgres fetchone() returns a list-like object; we grab index 0
        cur.execute('SELECT COUNT(*) FROM users')
        stats['total_users'] = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(*) FROM applications')
        stats['total_applications'] = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(*) FROM feedback')
        stats['total_feedback'] = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(*) FROM feedback WHERE rating=1')
        stats['thumbs_up'] = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(*) FROM feedback WHERE rating=0')
        stats['thumbs_down'] = cur.fetchone()[0]

        # 2. Events last 7 days (Handling Postgres vs SQLite dates)
        if USE_POSTGRES:
            event_query = '''SELECT event, COUNT(*) as cnt FROM events 
                             WHERE created_at >= CURRENT_DATE - INTERVAL '7 days' 
                             GROUP BY event ORDER BY cnt DESC'''
        else:
            event_query = '''SELECT event, COUNT(*) as cnt FROM events 
                             WHERE created_at >= datetime('now','-7 days') 
                             GROUP BY event ORDER BY cnt DESC'''
        
        cur.execute(event_query)
        stats['events_7d'] = [dict(r) for r in cur.fetchall()]

        # 3. Daily active sessions (last 14 days)
        if USE_POSTGRES:
            daily_query = '''SELECT created_at::date as day, COUNT(DISTINCT session_id) as sessions, 
                             COUNT(DISTINCT user_id) as users 
                             FROM events WHERE created_at >= CURRENT_DATE - INTERVAL '14 days' 
                             GROUP BY day ORDER BY day DESC'''
        else:
            daily_query = '''SELECT DATE(created_at) as day, COUNT(DISTINCT session_id) as sessions, 
                             COUNT(DISTINCT user_id) as users 
                             FROM events WHERE created_at >= datetime('now','-14 days') 
                             GROUP BY day ORDER BY day DESC'''
        
        cur.execute(daily_query)
        stats['daily_activity'] = [dict(r) for r in cur.fetchall()]

        # 4. Recent feedback
        cur.execute('SELECT rating, message, context, created_at FROM feedback ORDER BY created_at DESC LIMIT 20')
        stats['recent_feedback'] = [dict(r) for r in cur.fetchall()]

        # 5. Recent registrations
        cur.execute('SELECT email, name, created_at, last_seen FROM users ORDER BY created_at DESC LIMIT 20')
        stats['recent_users'] = [dict(r) for r in cur.fetchall()]

        cur.close()
        conn.close()
        return jsonify({'status': 'ok', **stats})
        
    except Exception as e:
        import traceback
        print(f"ADMIN STATS ERROR: {traceback.format_exc()}")
        return jsonify({'status': 'error', 'message': str(e)})

# ── HTML Template ──────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script>var FIRST_VISIT = {{ first_visit }};</script>
<title>CivilApply v5 — {{ name }}</title>
<!-- CivilApply v5-phase5 -->
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Fraunces:ital,wght@0,300;0,600;1,300&display=swap');

  :root {
    --bg:       #0e0f0c;
    --surface:  #161714;
    --border:   #2a2b27;
    --accent:   #c8f060;
    --accent2:  #f0a030;
    --text:     #e8e8e2;
    --muted:    #888880;
    --danger:   #f06050;
    --mono:     'DM Mono', monospace;
    --serif:    'Fraunces', Georgia, serif;
  }

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--mono);
    font-size: 13px;
    min-height: 100vh;
    line-height: 1.6;
  }

  /* ── Header ── */
  header {
    border-bottom: 1px solid var(--border);
    padding: 20px 40px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--surface);
  }

  .logo {
    font-family: var(--serif);
    font-size: 22px;
    font-weight: 600;
    color: var(--accent);
    letter-spacing: -0.5px;
  }
  .logo span { color: var(--muted); font-weight: 300; font-style: italic; }

  .meta {
    display: flex;
    gap: 12px;
    align-items: center;
  }
  .meta-item {
    color: var(--muted);
    font-size: 10px;
    letter-spacing: 0.3px;
  }
  .meta-item strong { color: var(--text); font-weight: 500; }
  /* CV status chip — shows name + years inline, compact */
  .cv-chip {
    display: none;
    align-items: center;
    gap: 6px;
    background: #0f1a0a;
    border: 1px solid var(--accent);
    border-radius: 2px;
    padding: 4px 10px;
    font-size: 10px;
    color: var(--accent);
    letter-spacing: 0.5px;
    white-space: nowrap;
    max-width: 220px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .cv-chip.active { display: flex; }
  /* Provider badge — subtle, not loud */
  .provider-badge {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--muted);
    padding: 3px 8px;
    border-radius: 2px;
    font-size: 9px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    white-space: nowrap;
  }
  /* User info pill */
  .user-pill {
    display: none;
    align-items: center;
    gap: 6px;
    font-size: 10px;
    color: var(--muted);
    max-width: 140px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .user-pill.active { display: flex; }

  /* ── Header CV upload button ── */
  .header-upload {
    display: flex;
    align-items: center;
    gap: 8px;
    border: 1px dashed var(--border);
    border-radius: 3px;
    padding: 6px 14px;
    cursor: pointer;
    transition: all 0.15s;
    background: transparent;
    font-family: var(--mono);
    color: var(--muted);
    font-size: 10px;
    letter-spacing: 1px;
    text-transform: uppercase;
    white-space: nowrap;
    user-select: none;
  }
  .header-upload:hover { border-color: var(--accent); color: var(--accent); }
  .header-upload.loaded { border-color: var(--accent); border-style: solid; background: #0f1a0a; color: var(--accent); }

  /* ── Layout ── */
  .workspace {
    display: grid;
    grid-template-columns: 1fr 1fr;
    height: calc(100vh - 65px);
    overflow: hidden;
  }

  /* ── Input Panel ── */
  .input-panel {
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    padding: 28px 32px;
    gap: 14px;
    overflow-y: auto;
    min-height: 0;
  }

  .panel-label {
    font-size: 10px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--muted);
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .panel-label::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
  }

  textarea {
    flex: 1;
    background: var(--bg);
    border: 1px solid var(--border);
    color: var(--text);
    font-family: var(--mono);
    font-size: 12px;
    line-height: 1.7;
    padding: 20px;
    resize: none;
    outline: none;
    border-radius: 3px;
    transition: border-color 0.2s;
  }
  textarea:focus { border-color: var(--accent); }
  textarea::placeholder { color: var(--muted); }

  .btn-generate {
    background: var(--accent);
    color: #0e0f0c;
    border: none;
    padding: 14px 28px;
    font-family: var(--mono);
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    cursor: pointer;
    border-radius: 2px;
    transition: all 0.15s;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }
  .btn-generate:hover { background: #d8ff70; transform: translateY(-1px); }
  .btn-generate:active { transform: translateY(0); }
  .btn-generate:disabled { background: var(--border); color: var(--muted); cursor: not-allowed; transform: none; }

  .spinner {
    width: 14px; height: 14px;
    border: 2px solid transparent;
    border-top-color: currentColor;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
    display: none;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  @keyframes pulse-border {
    0%, 100% { box-shadow: 0 0 0 0 rgba(200, 240, 96, 0.4); }
    50%       { box-shadow: 0 0 0 4px rgba(200, 240, 96, 0); }
  }

  /* ── Output Panel ── */
  .output-panel {
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    padding: 28px 32px 40px;
    gap: 20px;
    scroll-behavior: smooth;
  }

  .placeholder-msg {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: calc(100vh - 180px);
    gap: 12px;
    color: var(--muted);
    text-align: center;
  }
  .placeholder-msg .big { font-family: var(--serif); font-size: 48px; opacity: 0.15; }
  .placeholder-msg p { font-size: 11px; letter-spacing: 1px; text-transform: uppercase; }

  /* ── Result Sections ── */
  .result { display: none; }
  .result.visible { display: flex; flex-direction: column; gap: 24px; }

  .section {
    border: 1px solid var(--border);
    border-radius: 3px;
    overflow: hidden;
  }

  .section-head {
    background: var(--surface);
    padding: 10px 16px;
    font-size: 10px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--muted);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .section-body { padding: 16px; }

  /* ── Job Parsed Grid ── */
  .parsed-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px 24px;
  }
  .parsed-item { display: flex; flex-direction: column; gap: 2px; }
  .parsed-key {
    font-size: 9px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--muted);
  }
  .parsed-val {
    color: var(--text);
    font-size: 13px;
  }
  .email-val {
    color: var(--accent2);
    text-decoration: none;
  }
  .email-val:hover { text-decoration: underline; }

  .apply-email-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: #1a1f10;
    border: 1px solid var(--accent);
    color: var(--accent);
    padding: 8px 18px;
    border-radius: 2px;
    font-family: var(--mono);
    font-size: 12px;
    text-decoration: none;
    letter-spacing: 0.5px;
    transition: all 0.15s;
  }
  .apply-email-btn::before { content: "✉ "; }
  .apply-email-btn:hover {
    background: var(--accent);
    color: #0e0f0c;
  }

  /* ── Confidence Bar ── */
  .confidence-row {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 12px;
  }
  .conf-number {
    font-family: var(--serif);
    font-size: 36px;
    font-weight: 600;
    color: var(--accent);
    min-width: 56px;
    line-height: 1;
  }
  .conf-number.medium { color: var(--accent2); }
  .conf-number.low    { color: var(--danger); }
  .conf-bar-wrap {
    flex: 1;
    height: 6px;
    background: var(--border);
    border-radius: 3px;
    overflow: hidden;
  }
  .conf-bar {
    height: 100%;
    background: var(--accent);
    border-radius: 3px;
    transition: width 0.8s cubic-bezier(.16,1,.3,1);
    width: 0%;
  }
  .conf-bar.medium { background: var(--accent2); }
  .conf-bar.low    { background: var(--danger); }

  .verdict {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border-radius: 2px;
    font-size: 11px;
    letter-spacing: 1px;
    text-transform: uppercase;
    font-weight: 500;
    margin-top: 4px;
  }
  .verdict.apply   { background: #1a2510; border: 1px solid var(--accent); color: var(--accent); }
  .verdict.caution { background: #201a08; border: 1px solid var(--accent2); color: var(--accent2); }
  .verdict.skip    { background: #1f1210; border: 1px solid var(--danger); color: var(--danger); }

  .match-details {
    display: flex;
    gap: 16px;
    margin-top: 12px;
    flex-wrap: wrap;
  }
  .match-pill {
    background: var(--bg);
    border: 1px solid var(--border);
    padding: 4px 10px;
    border-radius: 2px;
    font-size: 10px;
    letter-spacing: 0.5px;
    color: var(--muted);
  }
  .match-pill span { color: var(--text); }

  /* ── Text Sections ── */
  .text-content {
    font-size: 13px;
    line-height: 1.75;
    color: var(--text);
    white-space: pre-wrap;
  }

  .copy-btn {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--muted);
    padding: 4px 12px;
    font-family: var(--mono);
    font-size: 10px;
    letter-spacing: 1px;
    text-transform: uppercase;
    cursor: pointer;
    border-radius: 2px;
    transition: all 0.15s;
  }
  .copy-btn:hover { border-color: var(--accent); color: var(--accent); }
  .copy-btn.copied { border-color: var(--accent); color: var(--accent); }

  .provider-tag {
    font-size: 9px;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: var(--muted);
    background: var(--bg);
    border: 1px solid var(--border);
    padding: 2px 8px;
    border-radius: 2px;
  }

  /* ── Rejected State ── */
  .rejected-msg {
    border: 1px solid var(--danger);
    background: #1f1210;
    border-radius: 3px;
    padding: 20px 24px;
    display: flex;
    gap: 16px;
    align-items: flex-start;
  }
  .rejected-icon { font-size: 24px; }
  .rejected-text h3 {
    color: var(--danger);
    font-family: var(--serif);
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 6px;
  }
  .rejected-text p { color: var(--muted); font-size: 12px; line-height: 1.6; }

  /* ── Error State ── */
  .error-box {
    border: 1px solid var(--danger);
    background: #1f1210;
    border-radius: 3px;
    padding: 16px 20px;
    color: var(--danger);
    font-size: 12px;
    display: none;
  }

  /* duplicate .apply-email-btn removed */
  .email-hint {
    margin-left: 12px;
    font-size: 10px;
    color: var(--muted);
    letter-spacing: 0.5px;
  }

  .download-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: var(--navy, #1a2744);
    border: 1px solid #3a4a6a;
    color: #8ab4f8;
    padding: 8px 18px;
    border-radius: 2px;
    font-family: var(--mono);
    font-size: 11px;
    letter-spacing: 1px;
    text-transform: uppercase;
    cursor: pointer;
    transition: all 0.15s;
    margin-top: 12px;
  }
  .download-btn:hover { background: #243660; border-color: #8ab4f8; }
  .download-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  /* ── CV Upload Panel ── */
  .upload-zone {
    border: 1.5px dashed var(--border);
    border-radius: 4px;
    padding: 14px 20px;
    display: flex;
    cursor: pointer;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    transition: border-color 0.2s, background 0.2s;
    cursor: pointer;
    background: rgba(255,255,255,0.02);
    flex-wrap: wrap;
    flex-shrink: 0;
  }
  .upload-zone:hover { border-color: var(--accent); background: rgba(188,255,60,0.03); }
  .upload-zone.has-cv {
    border-color: var(--accent);
    border-style: solid;
    background: #0f1a0a;
  }
  .upload-zone input[type="file"] { display: none; }
  .upload-label {
    font-size: 10px;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: var(--muted);
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
  }
  .upload-label .icon { font-size: 15px; }
  .cv-confirmed {
    font-size: 11px;
    color: var(--accent);
    display: none;
    gap: 6px;
    align-items: center;
  }
  .cv-confirmed.visible { display: flex; }
  .btn-upload {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--muted);
    padding: 5px 14px;
    font-family: var(--mono);
    font-size: 10px;
    letter-spacing: 1px;
    text-transform: uppercase;
    cursor: pointer;
    border-radius: 2px;
    transition: all 0.15s;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .btn-upload:hover { border-color: var(--accent); color: var(--accent); }

  /* ── Scrollbar ── */
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: var(--bg); }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
  /* ── Pulse animation ── */
  @keyframes pulse-text {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.45; }
  }

  /* ── Mobile ── */
  @media (max-width: 768px) {
    header { padding: 12px 16px; flex-wrap: wrap; gap: 8px; }
    .meta { gap: 8px; flex-wrap: wrap; font-size: 10px; }
    .meta-item { display: none; }
    /* Stack panels vertically on mobile */
    .workspace {
      grid-template-columns: 1fr;
      grid-template-rows: auto 1fr;
      height: auto;
      min-height: calc(100vh - 56px);
      overflow: visible;
    }
    .input-panel {
      border-right: none;
      border-bottom: 1px solid var(--border);
      padding: 16px;
      overflow-y: visible;
      height: auto;
    }
    .output-panel { padding: 16px 16px 32px; overflow-y: visible; }
    textarea { min-height: 120px; max-height: 220px; }
    /* Panels full-width on mobile */
    #tracker-panel, #batch-panel, #cv-editor-panel { width: 100vw !important; }
    /* Jobs grid single column */
    #jobs-grid { grid-template-columns: 1fr !important; padding: 10px 12px 20px !important; }
    .batch-card { flex-wrap: wrap; gap: 8px; }
    /* Buttons full-width */
    .btn-generate { padding: 14px; font-size: 13px; }
    .download-btn { padding: 12px; font-size: 11px; }
    /* Apply bar inputs */
    #apply-subject, #apply-body { font-size: 13px; }
    /* CV editor grid single column on mobile */
    #cv-tab-profile .cv-field-group[style*="grid-column"] { grid-column: 1 !important; }
    /* Tracker filter wrap */
    .tracker-filter-btn { padding: 4px 8px; font-size: 9px; }
    /* Welcome overlay */
    #welcome-overlay > div { padding: 28px 20px; }
    /* Section padding */
    .section-body { padding: 14px 16px; }
    .section-head { padding: 10px 16px; }
    /* Parsed grid */
    .parsed-grid { grid-template-columns: 1fr 1fr; }
    /* Hide non-essential header items */
    #tracker-nav-btn .tracker-count-badge { display: inline !important; }
  }
  @media (max-width: 480px) {
    .logo { font-size: 17px; }
    .parsed-grid { grid-template-columns: 1fr; }
    header { padding: 10px 12px; }
    .input-panel, .output-panel { padding: 12px; }
    .section-body { padding: 12px; }
    .section-head { padding: 10px 12px; font-size: 11px; }
    /* Stack download + edit buttons */
    #download-cv-btn, #edit-cv-btn { width: 100%; }
    /* Cover letter textarea readable */
    #apply-body { min-height: 160px; }
    /* Batch score label */
    #batch-score-label { font-size: 13px; }
  }

</style>
</head>
<body>

<header>
  <a href="/" class="logo" style="text-decoration:none;">Civil<span>Apply</span></a>

  <div class="meta">
    <!-- Hidden file input -->
    <input type="file" id="cv-file-input-hdr" accept=".pdf" style="display:none" onchange="uploadCV(this)">

    <!-- CV chip: shows after upload (replaces the upload button + candidate meta + years) -->
    <div id="cv-chip" class="cv-chip" onclick="document.getElementById('cv-file-input-hdr').click()" title="Click to replace CV">
      <span style="font-size:11px;">📄</span>
      <span id="cv-chip-name">{{ name }}</span>
      <span id="cv-chip-years" style="color:var(--muted);font-size:9px;"></span>
    </div>

    <!-- Upload prompt: shows before upload -->
    <label for="cv-file-input-hdr" class="header-upload" id="header-upload-btn" title="Upload your CV PDF">
      <span>📄</span>
      <span id="header-upload-text">Upload CV</span>
    </label>

    <!-- Provider badge: subtle, only when CV active -->
    <div class="provider-badge" id="provider-badge" style="display:none;">{{ provider }}</div>

    <!-- Tracker button -->
    <button onclick="showTracker()" id="tracker-nav-btn"
      style="background:transparent;border:1px solid var(--border);color:var(--muted);padding:5px 12px;
             font-family:var(--mono);font-size:10px;letter-spacing:1px;text-transform:uppercase;
             cursor:pointer;border-radius:2px;transition:all 0.15s;white-space:nowrap;"
      onmouseover="this.style.borderColor='var(--accent)';this.style.color='var(--accent)'"
      onmouseout="this.style.borderColor='var(--border)';this.style.color='var(--muted)'">
      Applications
      <span id="tracker-count-badge" style="display:none;background:var(--accent);color:#0e0f0c;border-radius:10px;padding:1px 6px;font-size:9px;margin-left:4px;font-weight:600;"></span>
    </button>

    <!-- Auth: email + account/logout -->
    <div id="auth-nav" style="display:flex;align-items:center;gap:8px;">
      <span id="auth-user-display" style="display:none;font-size:10px;color:var(--muted);
            max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"></span>
      <button id="auth-nav-btn" onclick="showAuth()"
        style="background:transparent;border:1px solid var(--border);color:var(--muted);
               padding:5px 12px;font-family:var(--mono);font-size:10px;cursor:pointer;
               border-radius:2px;letter-spacing:0.5px;transition:all 0.15s;white-space:nowrap;"
        onmouseover="this.style.borderColor='var(--accent)';this.style.color='var(--accent)'"
        onmouseout="this.style.borderColor='var(--border)';this.style.color='var(--muted)'">
        Sign In
      </button>
    </div>
  </div>
</header>

<div class="workspace">

  <!-- ── Input Panel ── -->
  <div class="input-panel">
    <!-- CV Upload Zone -->
    <div class="panel-label">Your CV</div>
    <input type="file" id="cv-file-input" accept=".pdf" style="display:none" onchange="uploadCV(this)">
    <label for="cv-file-input" class="upload-zone" id="upload-zone">
      <div class="upload-label">
        <span class="icon">📄</span>
        <span id="upload-label-text">Upload your CV PDF — output will use your profile</span>
      </div>
      <div class="cv-confirmed" id="cv-confirmed">
        <span>✓</span><span id="cv-name-display"></span>
      </div>
      <span class="btn-upload">Choose File</span>
    </label>

    <div class="panel-label">Job Description</div>
    <textarea id="jd-input"
      placeholder="Paste the job description here...&#10;&#10;Works best with LinkedIn, Jobberman, MyJobMag, or any Nigerian job board listing."></textarea>
    <div class="error-box" id="error-box"></div>
    <button class="btn-generate" id="gen-btn" onclick="generate()">
      <div class="spinner" id="spinner"></div>
      <span id="btn-label">Generate Application</span>
    </button>
  </div>

  <!-- ── Output Panel ── -->
  <div class="output-panel" id="output-panel">

    <div class="placeholder-msg" id="placeholder">
      <div class="big">⌗</div>
      <p>Paste a job description and click generate</p>
    </div>

    <div class="result" id="result">

      <!-- Rejected -->
      <div id="rejected-section" style="display:none">
        <div class="rejected-msg">
          <div class="rejected-icon">⛔</div>
          <div class="rejected-text">
            <h3>Not a Civil Engineering Role</h3>
            <p id="rejected-reason"></p>
          </div>
        </div>
      </div>

      <!-- Parsed Job -->
      <div class="section" id="parsed-section">
        <div class="section-head">
          <span>📋 Job Parsed</span>
        </div>
        <div class="section-body">
          <div class="parsed-grid">
            <div class="parsed-item">
              <div class="parsed-key">Title</div>
              <div class="parsed-val" id="p-title">—</div>
            </div>
            <div class="parsed-item">
              <div class="parsed-key">Years Required</div>
              <div class="parsed-val" id="p-years">—</div>
            </div>
            <div class="parsed-item">
              <div class="parsed-key">Project Types</div>
              <div class="parsed-val" id="p-projects">—</div>
            </div>
            <div class="parsed-item">
              <div class="parsed-key">Salary</div>
              <div class="parsed-val" id="p-salary">—</div>
            </div>
            <div class="parsed-item" id="p-email-row" style="display:none;grid-column:1/-1">
              <div class="parsed-key">Apply To</div>
              <div style="margin-top:8px;border:1px solid var(--border);border-radius:3px;overflow:hidden">
                <div style="padding:12px 16px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap">
                  <div>
                    <div style="font-size:11px;color:var(--muted);margin-bottom:2px">Send your CV to this address:</div>
                    <div id="p-email-text" style="color:var(--accent2);font-size:14px;letter-spacing:0.3px"></div>
                    <div style="font-size:10px;color:var(--muted);margin-top:4px">Subject: <span id="p-email-subject" style="color:var(--text)"></span></div>
                  </div>
                  <div style="display:flex;gap:8px">
                    <button class="copy-btn" id="copy-details-btn" onclick="copyEmailDetails()">Copy Address</button>
                  </div>
                </div>
                <div style="background:var(--surface);border-top:1px solid var(--border);padding:10px 16px;font-size:10px;color:var(--muted);display:flex;align-items:center;gap:8px">
                  <span>📋</span>
                  <span>Use <b style="color:var(--text)">Copy Cover Letter</b> button below → open Yahoo Mail → Compose → paste in body → attach CV → send</span>
                </div>
              </div>
            </div>
            <div class="parsed-item" id="p-skills-row" style="display:none">
              <div class="parsed-key">Skills Wanted</div>
              <div class="parsed-val" id="p-skills">—</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Match Analysis -->
      <div class="section" id="match-section">
        <div class="section-head"><span>🎯 Match Analysis</span></div>
        <div class="section-body">
          <div class="confidence-row">
            <div class="conf-number" id="conf-number">0</div>
            <div style="flex:1">
              <div style="font-size:10px;color:var(--muted);margin-bottom:6px;">CONFIDENCE SCORE / 100</div>
              <div class="conf-bar-wrap">
                <div class="conf-bar" id="conf-bar"></div>
              </div>
            </div>
          </div>
          <div id="verdict-box"></div>
          <div class="match-details" id="match-details"></div>
        </div>
      </div>

      <!-- CV Summary -->
      <div class="section" id="summary-section">
        <div class="section-head">
          <span>📄 Tailored CV Summary</span>
          <div style="display:flex;gap:8px;align-items:center">
            <span class="provider-tag" id="provider-tag">—</span>
            <button class="copy-btn" onclick="copyText('cv-summary-text', this)">Copy</button>
          </div>
        </div>
        <div class="section-body">
          <div class="text-content" id="cv-summary-text"></div>
          <div style="margin-top:12px;font-size:10px;color:var(--muted);letter-spacing:0.5px">
            ↑ Paste into the Profile/Summary section of your CV
          </div>
          <div style="display:flex;gap:8px;margin-top:4px;flex-wrap:wrap">
            <button class="download-btn" id="download-cv-btn" onclick="downloadCV()" disabled style="flex:1">
              ⬇ Download CV PDF
            </button>
            <button class="copy-btn" id="edit-cv-btn" onclick="showCvEditor()" disabled
              style="padding:10px 18px;font-size:11px;border-color:var(--accent);color:var(--accent)">
              ✏ Edit CV
            </button>
          </div>
        </div>
      </div>

      <!-- Cover Letter -->
      <div class="section" id="letter-section">
        <div class="section-head">
          <span>✉️ Cover Letter</span>
          <button class="copy-btn" onclick="copyText('cover-letter-text', this)">Copy</button>
        </div>
        <div class="section-body">
          <div class="text-content" id="cover-letter-text"></div>
          <div style="margin-top:12px;font-size:10px;color:var(--muted);letter-spacing:0.5px">
            ↑ Copy this and paste into your email body
          </div>
        </div>
      </div>

      <!-- ── Apply Bar ─────────────────────────────────────────────────── -->
      <div id="apply-bar" style="display:none;margin-top:0">
        <div class="section">
          <div class="section-head"><span>🚀 Apply for This Job</span></div>
          <div class="section-body">

            <!-- Email apply -->
            <div id="apply-email-section" style="display:none">
              <div style="font-size:11px;color:var(--muted);margin-bottom:8px">
                This employer accepts email applications. Your tailored CV will be attached automatically.
              </div>
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;flex-wrap:wrap">
                <span style="font-size:11px;color:var(--muted)">To:</span>
                <span id="apply-email-addr" style="color:var(--accent2);font-size:13px;font-weight:bold;letter-spacing:0.3px"></span>
                <button class="copy-btn" id="copy-apply-email-btn" onclick="copyApplyEmail()" style="padding:3px 10px;font-size:10px">Copy</button>
              </div>
              <div style="margin-bottom:6px">
                <label style="font-size:10px;color:var(--muted);display:block;margin-bottom:3px">Subject</label>
                <input id="apply-subject" type="text" style="width:100%;box-sizing:border-box;background:var(--surface);border:1px solid var(--border);color:var(--text);padding:7px 10px;font-family:inherit;font-size:12px;border-radius:2px;outline:none">
              </div>
              <div style="margin-bottom:10px">
                <label style="font-size:10px;color:var(--muted);display:block;margin-bottom:3px">Email body (cover letter pre-filled — edit if needed)</label>
                <textarea id="apply-body" rows="8" style="width:100%;box-sizing:border-box;background:var(--surface);border:1px solid var(--border);color:var(--text);padding:8px 10px;font-family:inherit;font-size:11px;resize:vertical;border-radius:2px;outline:none;line-height:1.5"></textarea>
              </div>
              <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
                <button id="send-app-btn" class="generate-btn" onclick="sendApplication()" style="padding:10px 24px;font-size:12px">
                  📤 Send Application
                </button>
                <span style="font-size:10px;color:var(--muted)">Your tailored CV PDF will be attached automatically</span>
              </div>
              <!-- SMTP setup hint -->
              <div id="smtp-setup-hint" style="display:none;margin-top:12px;padding:10px 14px;border:1px solid #f0a030;border-radius:3px;font-size:11px;color:#f0a030;line-height:1.6">
                <b>One-time setup needed to send emails:</b><br>
                Create a file called <code style="background:var(--surface);padding:1px 4px">.env</code> in your project folder and add:<br>
                <code style="background:var(--surface);padding:4px 8px;display:inline-block;margin-top:4px">SMTP_EMAIL=yourgmail@gmail.com<br>SMTP_PASSWORD=your-app-password</code><br>
                <span style="color:var(--muted)">Use a Gmail App Password (not your main password). 
                <a href="https://myaccount.google.com/apppasswords" target="_blank" style="color:#8ab4f8">Generate one here →</a></span>
              </div>
            </div>

            <!-- Platform apply -->
            <div id="apply-platform-section" style="display:none">
              <div style="font-size:11px;color:var(--muted);margin-bottom:12px">
                This job uses the platform's built-in apply system. Download your tailored CV first, then apply on the job board.
              </div>
              <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
                <a id="apply-platform-link" href="#" target="_blank" rel="noopener"
                   style="display:inline-block;background:var(--accent);color:var(--bg);padding:10px 20px;text-decoration:none;border-radius:2px;font-size:12px;font-weight:bold;font-family:inherit">
                  Apply on Job Board →
                </a>
                <span style="font-size:10px;color:var(--muted)">Download your CV above before clicking</span>
              </div>
            </div>

          </div>
        </div>
      </div>

    </div><!-- /result -->
  </div><!-- /output-panel -->
</div><!-- /workspace -->

<!-- ── Jobs Feed Panel ── -->
<div id="jobs-panel" style="display:none; border-top:1px solid var(--border); background:var(--surface);">
  <div style="padding:16px 40px 10px; display:flex; align-items:flex-start; justify-content:space-between; gap:16px; flex-wrap:wrap;">
    <div style="font-size:10px;letter-spacing:2px;text-transform:uppercase;color:var(--muted);">
      ⚡ Live Job Feed
    </div>
    <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">

      <!-- Profession filter -->
      <select id="profession-filter" onchange="loadJobs(false)"
        style="background:var(--surface);color:var(--text);border:1px solid var(--border);padding:4px 10px;font-family:var(--mono);font-size:10px;border-radius:2px;cursor:pointer;outline:none;">
        <option value="all">All Roles</option>
        <option value="civil_engineer">Civil / Structural Engineer</option>
        <option value="quantity_surveyor">Quantity Surveyor</option>
        <option value="architect">Architect</option>
        <option value="project_manager">Project Manager</option>
        <option value="hse_officer">HSE Officer</option>
        <option value="mep_engineer">M&amp;E / MEP Engineer</option>
        <option value="land_surveyor">Land Surveyor</option>
        <option value="site_supervisor">Site Supervisor / Foreman</option>
        <option value="contracts_manager">Contracts / Procurement</option>
      </select>

      <!-- Source checkboxes -->
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
        <label style="font-size:10px;color:var(--muted);display:flex;align-items:center;gap:4px;cursor:pointer;">
          <input type="checkbox" id="src-jobberman" checked onchange="loadJobs(false)" style="accent-color:#c8f060;"> <span style="color:#c8f060;">Jobberman</span>
        </label>
        <label style="font-size:10px;color:var(--muted);display:flex;align-items:center;gap:4px;cursor:pointer;">
          <input type="checkbox" id="src-myjobmag" checked onchange="loadJobs(false)" style="accent-color:#60c8f0;"> <span style="color:#60c8f0;">MyJobMag</span>
        </label>
        <label style="font-size:10px;color:var(--muted);display:flex;align-items:center;gap:4px;cursor:pointer;">
          <input type="checkbox" id="src-ngcareers" checked onchange="loadJobs(false)" style="accent-color:#f0a030;"> <span style="color:#f0a030;">NGCareers</span>
        </label>
        <label style="font-size:10px;color:var(--muted);display:flex;align-items:center;gap:4px;cursor:pointer;">
          <input type="checkbox" id="src-hotng" checked onchange="loadJobs(false)" style="accent-color:#f06080;"> <span style="color:#f06080;">HotNG</span>
        </label>
        <label style="font-size:10px;color:var(--muted);display:flex;align-items:center;gap:4px;cursor:pointer;">
          <input type="checkbox" id="src-linkedin" checked onchange="loadJobs(false)" style="accent-color:#0a66c2;"> <span style="color:#5b9bd5;">LinkedIn</span>
        </label>
      </div>

      <button id="refresh-jobs-btn" onclick="loadJobs(true)"
        style="background:var(--accent);color:#0e0f0c;border:none;padding:6px 16px;font-family:var(--mono);font-size:10px;letter-spacing:1px;text-transform:uppercase;cursor:pointer;border-radius:2px;">
        Refresh Jobs
      </button>
      <span id="jobs-status" style="font-size:10px;color:var(--muted);"></span>
    </div>
  </div>
  <div id="jobs-grid" style="padding:10px 40px 28px; display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:12px; max-height:500px; overflow-y:auto;"></div>
</div>

<div style="border-top:1px solid var(--border);padding:8px 40px;background:var(--surface);display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
  <button onclick="toggleJobsFeed()" id="feed-toggle-btn"
    style="background:transparent;border:1px solid var(--border);color:var(--muted);padding:5px 14px;font-family:var(--mono);font-size:10px;letter-spacing:1px;text-transform:uppercase;cursor:pointer;border-radius:2px;transition:all 0.15s;"
    onmouseover="this.style.borderColor='var(--accent)';this.style.color='var(--accent)'"
    onmouseout="this.style.borderColor='var(--border)';this.style.color='var(--muted)'">
    ⚡ Live Jobs
  </button>
  <button onclick="showBatchApply()"
    style="background:var(--accent);color:#0e0f0c;border:none;padding:5px 16px;font-family:var(--mono);font-size:10px;letter-spacing:1px;text-transform:uppercase;cursor:pointer;border-radius:2px;font-weight:600;transition:all 0.15s;"
    onmouseover="this.style.opacity='0.85'" onmouseout="this.style.opacity='1'">
    🚀 Batch Apply
  </button>
  <span style="font-size:10px;color:var(--muted);">Auto-send tailored CV to all matching jobs in one click</span>
</div>

<!-- ── Batch Apply Panel ──────────────────────────────────────────────── -->
<div id="batch-overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:200;backdrop-filter:blur(3px)" onclick="hideBatchApply()"></div>

<div id="batch-panel" style="display:none;position:fixed;top:0;right:0;width:min(780px,100vw);height:100vh;
     background:var(--bg);border-left:1px solid var(--border);z-index:201;
     flex-direction:column;transform:translateX(100%);transition:transform 0.25s ease">

  <!-- Header -->
  <div style="padding:20px 28px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;background:var(--surface)">
    <div>
      <div style="font-size:16px;font-weight:600;color:var(--accent)">🚀 Batch Apply</div>
      <div style="font-size:10px;color:var(--muted);margin-top:2px">Scan all jobs, pick the best matches, send your CV in one go</div>
    </div>
    <button onclick="hideBatchApply()" style="background:transparent;border:1px solid var(--border);color:var(--muted);padding:6px 12px;font-family:var(--mono);font-size:11px;cursor:pointer;border-radius:2px">✕ Close</button>
  </div>

  <!-- Controls -->
  <div style="padding:14px 28px;border-bottom:1px solid var(--border);display:flex;gap:16px;align-items:center;flex-wrap:wrap">
    <div>
      <label style="font-size:10px;color:var(--muted);display:block;margin-bottom:4px;letter-spacing:1px;text-transform:uppercase">Min Match Score</label>
      <div style="display:flex;align-items:center;gap:8px">
        <input type="range" id="batch-min-score" min="40" max="85" value="55" step="5"
          oninput="document.getElementById('batch-score-label').textContent=this.value+'%'"
          style="width:120px;accent-color:var(--accent)">
        <span id="batch-score-label" style="font-size:13px;color:var(--accent);font-weight:600;min-width:36px">55%</span>
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:6px">
      <input type="checkbox" id="batch-email-only" style="accent-color:var(--accent)">
      <label for="batch-email-only" style="font-size:11px;color:var(--muted);cursor:pointer">Email-apply jobs only</label>
    </div>
    <button onclick="runBatchPreview()" id="batch-scan-btn"
      style="background:var(--accent);color:#0e0f0c;border:none;padding:8px 20px;font-family:var(--mono);font-size:11px;font-weight:600;letter-spacing:1px;cursor:pointer;border-radius:2px;text-transform:uppercase">
      🔍 Scan Jobs
    </button>
  </div>

  <!-- Results -->
  <div id="batch-results" style="flex:1;overflow-y:auto;padding:16px 28px">
    <div id="batch-idle" style="text-align:center;padding:60px 20px;color:var(--muted)">
      <div style="font-size:36px;margin-bottom:12px">🎯</div>
      <div style="font-size:13px">Click "Scan Jobs" to find your best matches</div>
      <div style="font-size:11px;margin-top:6px">We'll scrape Jobberman + MyJobMag, score each job against your CV, and show only the ones worth applying to</div>
    </div>
    <div id="batch-loading" style="display:none;text-align:center;padding:40px;color:var(--muted)">
      <div style="font-size:24px;margin-bottom:8px;animation:spin 1s linear infinite;display:inline-block">⟳</div>
      <div style="font-size:12px;margin-top:8px" id="batch-loading-msg">Scanning jobs...</div>
    </div>
    <div id="batch-list" style="display:none">
      <div id="batch-summary-bar" style="margin-bottom:12px;padding:10px 14px;background:var(--surface);border:1px solid var(--border);border-radius:3px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
        <span id="batch-summary-text" style="font-size:11px;color:var(--text)"></span>
        <div style="display:flex;gap:8px;align-items:center">
          <label style="font-size:10px;color:var(--muted)">
            <input type="checkbox" id="batch-select-all" onchange="batchSelectAll(this.checked)" style="accent-color:var(--accent)"> Select all
          </label>
          <button onclick="sendBatchSelected()" id="batch-send-btn"
            style="background:var(--accent);color:#0e0f0c;border:none;padding:7px 18px;font-family:var(--mono);font-size:11px;font-weight:700;cursor:pointer;border-radius:2px;letter-spacing:0.5px">
            📤 Send Selected
          </button>
        </div>
      </div>
      <div id="batch-cards"></div>
    </div>
  </div>
</div>

<style>
.batch-card {
  border:1px solid var(--border);border-radius:3px;padding:12px 14px;
  margin-bottom:8px;background:var(--surface);display:flex;align-items:center;gap:12px;
  transition:border-color 0.15s;
}
.batch-card:hover { border-color:#444; }
.batch-card.selected { border-color:var(--accent);background:#0d1a08; }
.conf-bar-bg { background:#1a1a1a;border-radius:2px;height:4px;width:80px;flex-shrink:0; }
.conf-bar-fill { height:4px;border-radius:2px;background:var(--accent);transition:width 0.3s; }
</style>

<!-- ── Application Tracker Panel ────────────────────────────────────── -->
<div id="tracker-overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:100;backdrop-filter:blur(2px)" onclick="hideTracker()"></div>

<div id="tracker-panel" style="display:none;position:fixed;top:0;right:0;width:min(720px,100vw);height:100vh;
     background:var(--bg);border-left:1px solid var(--border);z-index:101;
     display:flex;flex-direction:column;transform:translateX(100%);transition:transform 0.25s ease">

  <!-- Header -->
  <div style="padding:20px 28px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;background:var(--surface)">
    <div>
      <div style="font-size:16px;font-weight:600;color:var(--accent)">📋 My Applications</div>
      <div style="font-size:10px;color:var(--muted);margin-top:2px">Track every job you've applied to</div>
    </div>
    <div style="display:flex;gap:10px;align-items:center">
      <div id="tracker-stats" style="font-size:10px;color:var(--muted);text-align:right"></div>
      <button onclick="hideTracker()"
        style="background:transparent;border:1px solid var(--border);color:var(--muted);
               padding:6px 12px;font-family:var(--mono);font-size:11px;cursor:pointer;border-radius:2px">✕ Close</button>
    </div>
  </div>

  <!-- Filter bar -->
  <div style="padding:12px 28px;border-bottom:1px solid var(--border);display:flex;gap:8px;flex-wrap:wrap;align-items:center">
    <span style="font-size:10px;color:var(--muted);letter-spacing:1px;text-transform:uppercase">Filter:</span>
    <button class="tracker-filter-btn active" onclick="filterTracker('All', this)">All</button>
    <button class="tracker-filter-btn" onclick="filterTracker('Applied', this)">Applied</button>
    <button class="tracker-filter-btn" onclick="filterTracker('Interview', this)">Interview</button>
    <button class="tracker-filter-btn" onclick="filterTracker('Offer', this)">Offer</button>
    <button class="tracker-filter-btn" onclick="filterTracker('Rejected', this)">Rejected</button>
    <button class="tracker-filter-btn" onclick="filterTracker('Withdrawn', this)">Withdrawn</button>
  </div>

  <!-- List -->
  <div id="tracker-list" style="flex:1;overflow-y:auto;padding:16px 28px;display:flex;flex-direction:column;gap:10px">
    <div id="tracker-empty" style="display:none;text-align:center;padding:60px 20px;color:var(--muted)">
      <div style="font-size:40px;margin-bottom:12px">📭</div>
      <div style="font-size:13px">No applications yet</div>
      <div style="font-size:11px;margin-top:6px">Use "Use This Job" → Generate → Apply to start tracking</div>
    </div>
    <div id="tracker-loading" style="text-align:center;padding:40px;color:var(--muted);font-size:12px">Loading...</div>
  </div>

  <!-- Footer: manual add -->
  <div style="padding:14px 28px;border-top:1px solid var(--border);background:var(--surface)">
    <div style="font-size:10px;color:var(--muted);margin-bottom:8px;letter-spacing:1px;text-transform:uppercase">+ Add manually</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <input id="manual-title" placeholder="Job title *" style="flex:2;min-width:120px;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:7px 10px;font-family:var(--mono);font-size:11px;border-radius:2px;outline:none">
      <input id="manual-company" placeholder="Company" style="flex:1;min-width:100px;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:7px 10px;font-family:var(--mono);font-size:11px;border-radius:2px;outline:none">
      <input id="manual-url" placeholder="Job URL (optional)" style="flex:2;min-width:140px;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:7px 10px;font-family:var(--mono);font-size:11px;border-radius:2px;outline:none">
      <button onclick="manualAddApplication()"
        style="background:var(--accent);color:#0e0f0c;border:none;padding:7px 16px;font-family:var(--mono);font-size:11px;font-weight:600;cursor:pointer;border-radius:2px;white-space:nowrap">
        + Add
      </button>
    </div>
  </div>
</div>

<style>
.tracker-filter-btn {
  background:transparent;border:1px solid var(--border);color:var(--muted);
  padding:4px 10px;font-family:var(--mono);font-size:10px;letter-spacing:0.5px;
  cursor:pointer;border-radius:2px;transition:all 0.1s;text-transform:uppercase;
}
.tracker-filter-btn:hover { border-color:var(--accent);color:var(--accent); }
.tracker-filter-btn.active { background:var(--accent);color:#0e0f0c;border-color:var(--accent); }
.tracker-card {
  border:1px solid var(--border);border-radius:3px;padding:14px 16px;
  background:var(--surface);transition:border-color 0.15s;
}
.tracker-card:hover { border-color:#444; }
.status-pill {
  display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;letter-spacing:0.5px;
}
.status-Applied   { background:#0d2a1a;color:#4cde80;border:1px solid #1a5c30; }
.status-Interview { background:#1a1a00;color:#f0d030;border:1px solid #4a4a00; }
.status-Offer     { background:#0a1a2a;color:#60b0ff;border:1px solid #1a3a5a; }
.status-Rejected  { background:#2a0a0a;color:#f06060;border:1px solid #5a1a1a; }
.status-Withdrawn { background:#1a1a1a;color:#888;border:1px solid #333; }
</style>

<!-- ── Auth Modal ─────────────────────────────────────────────────────── -->
<div id="auth-overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.82);
     z-index:500;backdrop-filter:blur(4px);align-items:center;justify-content:center"
     onclick="if(event.target===this)hideAuth()">
  <div style="background:var(--surface);border:1px solid var(--border);border-radius:4px;
              padding:36px 40px;max-width:400px;width:90vw">

    <!-- Tabs -->
    <div style="display:flex;gap:0;border-bottom:1px solid var(--border);margin-bottom:24px">
      <button class="auth-tab active" id="auth-tab-login" onclick="switchAuthTab('login')">Sign In</button>
      <button class="auth-tab" id="auth-tab-register" onclick="switchAuthTab('register')">Create Account</button>
    </div>

    <!-- Login form -->
    <div id="auth-login-form">
      <div class="cv-field-group" style="margin-bottom:14px">
        <label class="cv-label">Email</label>
        <input class="cv-input" id="auth-login-email" type="email" placeholder="your@email.com" onkeydown="if(event.key==='Enter')doLogin()">
      </div>
      <div class="cv-field-group" style="margin-bottom:20px">
        <label class="cv-label">Password</label>
        <input class="cv-input" id="auth-login-password" type="password" placeholder="••••••••" onkeydown="if(event.key==='Enter')doLogin()">
      </div>
      <div id="auth-login-error" style="font-size:11px;color:#f06060;margin-bottom:12px;display:none"></div>
      <button onclick="doLogin()" id="auth-login-btn"
        style="width:100%;background:var(--accent);color:#0e0f0c;border:none;padding:12px;
               font-family:var(--mono);font-size:12px;font-weight:600;cursor:pointer;border-radius:2px">
        Sign In
      </button>
    </div>

    <!-- Register form -->
    <div id="auth-register-form" style="display:none">
      <div class="cv-field-group" style="margin-bottom:14px">
        <label class="cv-label">Your Name</label>
        <input class="cv-input" id="auth-reg-name" type="text" placeholder="First Last">
      </div>
      <div class="cv-field-group" style="margin-bottom:14px">
        <label class="cv-label">Email</label>
        <input class="cv-input" id="auth-reg-email" type="email" placeholder="your@email.com">
      </div>
      <div class="cv-field-group" style="margin-bottom:20px">
        <label class="cv-label">Password (min 8 characters)</label>
        <input class="cv-input" id="auth-reg-password" type="password" placeholder="••••••••" onkeydown="if(event.key==='Enter')doRegister()">
      </div>
      <div id="auth-reg-error" style="font-size:11px;color:#f06060;margin-bottom:12px;display:none"></div>
      <button onclick="doRegister()" id="auth-reg-btn"
        style="width:100%;background:var(--accent);color:#0e0f0c;border:none;padding:12px;
               font-family:var(--mono);font-size:12px;font-weight:600;cursor:pointer;border-radius:2px">
        Create Account
      </button>
    </div>

    <div style="text-align:center;margin-top:14px;font-size:10px;color:var(--muted)">
      Your CV stays private. No spam. <button onclick="hideAuth()" style="background:none;border:none;color:var(--muted);font-family:var(--mono);font-size:10px;cursor:pointer;text-decoration:underline">Cancel</button>
    </div>
  </div>
</div>

<!-- ── Feedback Prompt ─────────────────────────────────────────────────── -->
<div id="feedback-bar" style="display:none;position:fixed;bottom:0;left:0;right:0;z-index:200;
     background:var(--surface);border-top:1px solid var(--border);padding:14px 24px;
     display:none;align-items:center;gap:16px;flex-wrap:wrap">
  <span style="font-size:12px;color:var(--text);flex:1;min-width:180px">
    Was this CV tailoring useful?
  </span>
  <div style="display:flex;gap:8px;align-items:center">
    <button onclick="sendFeedback(1,this)" title="Yes, helpful"
      style="background:transparent;border:1px solid var(--border);color:var(--text);
             padding:6px 16px;font-size:16px;cursor:pointer;border-radius:2px;transition:all 0.15s"
      onmouseover="this.style.borderColor='var(--accent)'" onmouseout="this.style.borderColor='var(--border)'">👍</button>
    <button onclick="sendFeedback(0,this)" title="Not helpful"
      style="background:transparent;border:1px solid var(--border);color:var(--text);
             padding:6px 16px;font-size:16px;cursor:pointer;border-radius:2px;transition:all 0.15s"
      onmouseover="this.style.borderColor='#f06060'" onmouseout="this.style.borderColor='var(--border)'">👎</button>
    <input id="feedback-msg" placeholder="Optional comment..." maxlength="300"
      style="background:var(--bg);border:1px solid var(--border);color:var(--text);
             padding:6px 12px;font-family:var(--mono);font-size:11px;border-radius:2px;
             outline:none;width:220px"
      onkeydown="if(event.key==='Enter'&&this.value)sendFeedback(-1,null)">
    <button onclick="hideFeedbackBar()"
      style="background:transparent;border:none;color:var(--muted);font-size:16px;cursor:pointer;padding:4px">✕</button>
  </div>
</div>

<style>
.auth-tab {
  background:transparent;border:none;border-bottom:2px solid transparent;
  color:var(--muted);padding:10px 18px;font-family:var(--mono);font-size:11px;
  letter-spacing:0.5px;cursor:pointer;transition:all 0.15s;text-transform:uppercase;
}
.auth-tab:hover  { color:var(--text); }
.auth-tab.active { color:var(--accent);border-bottom-color:var(--accent); }
</style>

<!-- ── CV Editor Panel ───────────────────────────────────────────────── -->
<div id="cv-editor-overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:300;backdrop-filter:blur(3px)" onclick="hideCvEditor()"></div>

<div id="cv-editor-panel" style="display:none;position:fixed;top:0;right:0;width:min(820px,100vw);height:100vh;
     background:var(--bg);border-left:1px solid var(--border);z-index:301;
     flex-direction:column;transform:translateX(100%);transition:transform 0.25s ease">

  <!-- Header -->
  <div style="padding:18px 28px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;background:var(--surface);flex-shrink:0">
    <div>
      <div style="font-size:16px;font-weight:600;color:var(--accent)">✏ Edit Your CV</div>
      <div style="font-size:10px;color:var(--muted);margin-top:2px">Changes apply to this session — download to save permanently</div>
    </div>
    <div style="display:flex;gap:8px">
      <button onclick="saveCvEditor()" id="cv-save-btn"
        style="background:var(--accent);color:#0e0f0c;border:none;padding:8px 20px;
               font-family:var(--mono);font-size:11px;font-weight:600;cursor:pointer;border-radius:2px">
        💾 Save Changes
      </button>
      <button onclick="hideCvEditor()"
        style="background:transparent;border:1px solid var(--border);color:var(--muted);
               padding:8px 14px;font-family:var(--mono);font-size:11px;cursor:pointer;border-radius:2px">✕</button>
    </div>
  </div>

  <!-- Tabs -->
  <div style="display:flex;border-bottom:1px solid var(--border);background:var(--surface);flex-shrink:0">
    <button class="cv-tab active" onclick="switchCvTab('profile',this)">👤 Profile</button>
    <button class="cv-tab" onclick="switchCvTab('experience',this)">💼 Experience</button>
    <button class="cv-tab" onclick="switchCvTab('education',this)">🎓 Education</button>
    <button class="cv-tab" onclick="switchCvTab('skills',this)">🔧 Skills</button>
  </div>

  <!-- Content -->
  <div id="cv-editor-content" style="flex:1;overflow-y:auto;padding:24px 28px">

    <!-- Profile Tab -->
    <div id="cv-tab-profile" class="cv-tab-pane">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
        <div class="cv-field-group" style="grid-column:1/-1">
          <label class="cv-label">Full Name</label>
          <input class="cv-input" id="cvp-name" placeholder="Your full name">
        </div>
        <div class="cv-field-group" style="grid-column:1/-1">
          <label class="cv-label">Professional Title</label>
          <input class="cv-input" id="cvp-title" placeholder="e.g. Civil Engineer">
        </div>
        <div class="cv-field-group">
          <label class="cv-label">Email</label>
          <input class="cv-input" id="cvp-email" type="email" placeholder="your@email.com">
        </div>
        <div class="cv-field-group">
          <label class="cv-label">Phone</label>
          <input class="cv-input" id="cvp-phone" placeholder="+234...">
        </div>
        <div class="cv-field-group">
          <label class="cv-label">Location</label>
          <input class="cv-input" id="cvp-location" placeholder="City, State">
        </div>
        <div class="cv-field-group">
          <label class="cv-label">Years of Experience</label>
          <input class="cv-input" id="cvp-years" type="number" min="0" max="50" placeholder="e.g. 8">
        </div>
        <div class="cv-field-group" style="grid-column:1/-1">
          <label class="cv-label">LinkedIn URL</label>
          <input class="cv-input" id="cvp-linkedin" placeholder="linkedin.com/in/yourname">
        </div>
      </div>
    </div>

    <!-- Experience Tab -->
    <div id="cv-tab-experience" class="cv-tab-pane" style="display:none">
      <div id="cv-exp-list"></div>
      <button onclick="addCvExperience()"
        style="margin-top:12px;background:transparent;border:1px dashed var(--border);color:var(--muted);
               padding:10px;width:100%;font-family:var(--mono);font-size:11px;cursor:pointer;border-radius:2px;
               transition:all 0.15s"
        onmouseover="this.style.borderColor='var(--accent)';this.style.color='var(--accent)'"
        onmouseout="this.style.borderColor='var(--border)';this.style.color='var(--muted)'">
        + Add Experience
      </button>
    </div>

    <!-- Education Tab -->
    <div id="cv-tab-education" class="cv-tab-pane" style="display:none">
      <div id="cv-edu-list"></div>
      <button onclick="addCvEducation()"
        style="margin-top:12px;background:transparent;border:1px dashed var(--border);color:var(--muted);
               padding:10px;width:100%;font-family:var(--mono);font-size:11px;cursor:pointer;border-radius:2px;
               transition:all 0.15s"
        onmouseover="this.style.borderColor='var(--accent)';this.style.color='var(--accent)'"
        onmouseout="this.style.borderColor='var(--border)';this.style.color='var(--muted)'">
        + Add Education
      </button>
    </div>

    <!-- Skills Tab -->
    <div id="cv-tab-skills" class="cv-tab-pane" style="display:none">
      <div style="font-size:11px;color:var(--muted);margin-bottom:12px">One skill per line</div>
      <textarea id="cv-skills-input" rows="16"
        style="width:100%;box-sizing:border-box;background:var(--surface);border:1px solid var(--border);
               color:var(--text);padding:12px;font-family:var(--mono);font-size:12px;
               resize:vertical;border-radius:2px;outline:none;line-height:1.8"
        placeholder="Site supervision&#10;AutoCAD&#10;Reinforced concrete&#10;..."></textarea>
    </div>

  </div>

  <!-- Save indicator -->
  <div id="cv-save-indicator" style="display:none;padding:10px 28px;background:#0d2a1a;
       border-top:1px solid var(--accent);font-size:11px;color:var(--accent);text-align:center;flex-shrink:0">
    ✓ Changes saved — download your CV to use them
  </div>
</div>

<style>
.cv-tab {
  background:transparent;border:none;border-bottom:2px solid transparent;
  color:var(--muted);padding:12px 20px;font-family:var(--mono);font-size:11px;
  letter-spacing:0.5px;cursor:pointer;transition:all 0.15s;text-transform:uppercase;
}
.cv-tab:hover { color:var(--text); }
.cv-tab.active { color:var(--accent);border-bottom-color:var(--accent); }
.cv-tab-pane {}
.cv-field-group { display:flex;flex-direction:column;gap:5px; }
.cv-label { font-size:10px;color:var(--muted);letter-spacing:1px;text-transform:uppercase; }
.cv-input {
  background:var(--surface);border:1px solid var(--border);color:var(--text);
  padding:9px 12px;font-family:var(--mono);font-size:12px;border-radius:2px;
  outline:none;transition:border-color 0.15s;width:100%;box-sizing:border-box;
}
.cv-input:focus { border-color:var(--accent); }
.cv-exp-card, .cv-edu-card {
  border:1px solid var(--border);border-radius:3px;padding:16px;
  margin-bottom:12px;background:var(--surface);
}
.cv-exp-card:hover, .cv-edu-card:hover { border-color:#444; }
.cv-bullet-row { display:flex;gap:6px;align-items:flex-start;margin-bottom:6px; }
.cv-bullet-input {
  flex:1;background:var(--bg);border:1px solid var(--border);color:var(--text);
  padding:6px 10px;font-family:var(--mono);font-size:11px;border-radius:2px;
  outline:none;line-height:1.5;
}
.cv-bullet-input:focus { border-color:var(--accent); }
</style>

<!-- ── Welcome / Upload Prompt Overlay ──────────────────────────────── -->
<div id="welcome-overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.82);
     z-index:400;backdrop-filter:blur(4px);align-items:center;justify-content:center">
  <div style="background:var(--surface);border:1px solid var(--border);border-radius:4px;
              padding:40px 44px;max-width:480px;width:90vw;text-align:center">

    <div style="font-family:var(--serif);font-size:28px;color:var(--accent);margin-bottom:6px">
      Civil<span style="color:var(--muted);font-weight:300;font-style:italic">Apply</span>
    </div>
    <div style="font-size:12px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-bottom:28px">
      AI-powered CV tailoring for civil engineers
    </div>

    <div style="border:1px solid var(--border);border-radius:3px;padding:20px;margin-bottom:24px;text-align:left">
      <div style="font-size:10px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-bottom:12px">How it works</div>
      <div style="display:flex;flex-direction:column;gap:10px">
        <div style="display:flex;gap:12px;align-items:flex-start">
          <span style="color:var(--accent);font-size:16px;flex-shrink:0">①</span>
          <span style="font-size:12px;color:var(--text);line-height:1.5">Upload your CV — we extract your profile, experience and skills</span>
        </div>
        <div style="display:flex;gap:12px;align-items:flex-start">
          <span style="color:var(--accent);font-size:16px;flex-shrink:0">②</span>
          <span style="font-size:12px;color:var(--text);line-height:1.5">Paste any civil engineering job description</span>
        </div>
        <div style="display:flex;gap:12px;align-items:flex-start">
          <span style="color:var(--accent);font-size:16px;flex-shrink:0">③</span>
          <span style="font-size:12px;color:var(--text);line-height:1.5">Get a tailored CV summary + cover letter matched to that job</span>
        </div>
      </div>
    </div>

    <input type="file" id="welcome-cv-input" accept=".pdf" style="display:none" onchange="welcomeUpload(this)">
    <label for="welcome-cv-input"
      style="display:block;background:var(--accent);color:#0e0f0c;padding:14px 28px;
             border-radius:2px;font-family:var(--mono);font-size:13px;font-weight:600;
             letter-spacing:1px;text-transform:uppercase;cursor:pointer;transition:all 0.15s;margin-bottom:12px"
      onmouseover="this.style.background='#d8ff70'" onmouseout="this.style.background='var(--accent)'">
      📄 Upload Your CV to Get Started
    </label>

    <div id="welcome-upload-status" style="font-size:11px;color:var(--muted);min-height:18px"></div>

    <button onclick="skipWelcome()"
      style="margin-top:16px;background:transparent;border:none;color:var(--muted);
             font-family:var(--mono);font-size:10px;cursor:pointer;letter-spacing:0.5px;
             text-decoration:underline;text-underline-offset:3px">
      Skip — I'll upload later
    </button>
  </div>
</div>

<script src="/static/app.js"></script>

</body>
</html>"""

if __name__ == '__main__':
    print("\n  ══════════════════════════════════════════")
    print("    CivilApply — Web Interface")
    print("  ══════════════════════════════════════════")
    print(f"  Candidate : {BASE_CV['profile']['name']}")
    print(f"  Open      : http://localhost:5000")
    print(f"  Stop      : Ctrl+C")
    print("  ══════════════════════════════════════════\n")
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
