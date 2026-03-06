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

_load_env()

from flask import Flask, request, jsonify, render_template_string

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

# In-memory CV store keyed by session id (resets on server restart)
# For production this would be a database
_SESSION_CVS: dict = {}

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
def index():
    profile  = BASE_CV.get('profile', {})
    groq_key = os.environ.get('GROQ_API_KEY', '')
    cohere_key = os.environ.get('COHERE_API_KEY', '')
    if cohere_key:
        provider_label = 'Cohere AI — FREE'
    elif groq_key:
        provider_label = 'Groq AI — FREE'
    else:
        provider_label = 'Rule-based'
    return render_template_string(HTML_TEMPLATE,
        name=profile.get('name', ''),
        years=profile.get('experience_years', ''),
        provider=provider_label,
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

        parsed_cv = parse_cv_from_bytes(pdf_bytes, f.filename)

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
        _SESSION_CVS[sid] = parsed_cv

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
        active_cv  = _SESSION_CVS.get(sid) if sid else None
        active_cv  = active_cv or BASE_CV
        candidate  = active_cv.get('profile', {}).get('name', 'Candidate').replace(' ', '_')
        tmp_path   = os.path.join(tempfile.gettempdir(), f"cv_{job_title}.pdf")
        generate_cv_pdf(active_cv, tmp_path, cv_summary=cv_summary)
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
        cv_override = _SESSION_CVS.get(sid) if sid else None
        result = run_pipeline(raw_text, cv_override=cv_override)
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e), 'trace': traceback.format_exc()})


@app.route('/scrape-jobs', methods=['POST'])
def scrape_jobs():
    """Fetch live civil engineering jobs from Jobberman and MyJobMag."""
    if not _check_rate(request.remote_addr):
        return jsonify({'status': 'error', 'message': 'Too many requests. Please wait.'})
    try:
        from civil_engineering.scraper.job_scraper import fetch_jobs
        data          = request.get_json() or {}
        sources       = data.get('sources', ['jobberman', 'myjobmag'])
        max_pages     = min(int(data.get('max_pages', 2)), 3)   # cap at 3
        force_refresh = bool(data.get('force_refresh', False))
        jobs = fetch_jobs(sources=sources, max_pages=max_pages, force_refresh=force_refresh)
        return jsonify({'status': 'ok', 'jobs': jobs, 'count': len(jobs),
                        'cached': not force_refresh})
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
        active_cv = _SESSION_CVS.get(sid) if sid else None
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



# ── Application Tracker ────────────────────────────────────────────────────────

def _tracker_db():
    """Return a sqlite3 connection to the applications tracker DB."""
    import sqlite3
    db_path = os.path.join(DATA_DIR, 'applications.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute('''CREATE TABLE IF NOT EXISTS applications (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
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
    conn.commit()
    return conn


@app.route('/tracker/add', methods=['POST'])
def tracker_add():
    """Log a job application to the tracker."""
    data    = request.get_json() or {}
    title   = data.get('title', '').strip()
    if not title:
        return jsonify({'status': 'error', 'message': 'Job title required'})
    try:
        conn = _tracker_db()
        conn.execute(
            '''INSERT INTO applications (title, company, location, salary, url, platform, method, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (title,
             data.get('company', ''),
             data.get('location', ''),
             data.get('salary', ''),
             data.get('url', ''),
             data.get('platform', ''),
             data.get('method', ''),
             data.get('status', 'Applied'),
             data.get('notes', ''))
        )
        conn.commit()
        conn.close()
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/tracker/list', methods=['GET'])
def tracker_list():
    """Return all tracked applications as JSON."""
    try:
        conn = _tracker_db()
        rows = conn.execute('SELECT * FROM applications ORDER BY applied_at DESC').fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/tracker/update', methods=['POST'])
def tracker_update():
    """Update status or notes on an application."""
    data = request.get_json() or {}
    app_id = data.get('id')
    if not app_id:
        return jsonify({'status': 'error', 'message': 'ID required'})
    try:
        conn  = _tracker_db()
        field = data.get('field', 'status')
        if field not in ('status', 'notes'):
            return jsonify({'status': 'error', 'message': 'Invalid field'})
        conn.execute(f'UPDATE applications SET {field} = ? WHERE id = ?',
                     (data.get('value', ''), app_id))
        conn.commit()
        conn.close()
        return jsonify({'status': 'ok'})
    except Exception as e:
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
        conn.execute('DELETE FROM applications WHERE id = ?', (app_id,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# ── HTML Template ──────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
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
    gap: 24px;
    align-items: center;
  }
  .meta-item {
    color: var(--muted);
    font-size: 11px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }
  .meta-item strong { color: var(--text); }
  .provider-badge {
    background: #1a2010;
    border: 1px solid var(--accent);
    color: var(--accent);
    padding: 3px 10px;
    border-radius: 2px;
    font-size: 10px;
    letter-spacing: 1px;
    text-transform: uppercase;
  }

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
</style>
</head>
<body>

<header>
  <div class="logo">Civil<span>Apply</span></div>
  <div class="meta">
    <input type="file" id="cv-file-input-hdr" accept=".pdf" style="display:none" onchange="uploadCV(this)">
    <label for="cv-file-input-hdr" class="header-upload" id="header-upload-btn" title="Upload your CV PDF">
      <span>📄</span>
      <span id="header-upload-text">Upload CV</span>
    </label>
    <div class="meta-item">Candidate: <strong id="candidate-name">{{ name }}</strong></div>
    <div class="meta-item">Experience: <strong id="candidate-years">{{ years }}</strong> yrs</div>
    <div class="provider-badge">{{ provider }}</div>
    <button onclick="showTracker()" id="tracker-nav-btn"
      style="background:transparent;border:1px solid var(--border);color:var(--muted);padding:5px 14px;
             font-family:var(--mono);font-size:10px;letter-spacing:1px;text-transform:uppercase;
             cursor:pointer;border-radius:2px;transition:all 0.15s;white-space:nowrap;"
      onmouseover="this.style.borderColor='var(--accent)';this.style.color='var(--accent)'"
      onmouseout="this.style.borderColor='var(--border)';this.style.color='var(--muted)'">
      📋 My Applications <span id="tracker-count-badge" style="display:none;background:var(--accent);color:#0e0f0c;border-radius:10px;padding:1px 6px;font-size:9px;margin-left:4px"></span>
    </button>
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
          <button class="download-btn" id="download-cv-btn" onclick="downloadCV()" disabled>
            ⬇ Download Tailored CV PDF
          </button>
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
  <div style="padding:20px 40px 10px; display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap;">
    <div style="font-size:10px;letter-spacing:2px;text-transform:uppercase;color:var(--muted);">
      ⚡ Live Job Feed
    </div>
    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
      <label style="font-size:10px;color:var(--muted);display:flex;align-items:center;gap:6px;">
        <input type="checkbox" id="src-jobberman" checked> Jobberman
      </label>
      <label style="font-size:10px;color:var(--muted);display:flex;align-items:center;gap:6px;">
        <input type="checkbox" id="src-myjobmag" checked> MyJobMag
      </label>
      <button id="refresh-jobs-btn" onclick="loadJobs(true)" style="background:var(--accent);color:#0e0f0c;border:none;padding:6px 16px;font-family:var(--mono);font-size:10px;letter-spacing:1px;text-transform:uppercase;cursor:pointer;border-radius:2px;">
        Refresh Jobs
      </button>
      <span id="jobs-status" style="font-size:10px;color:var(--muted);"></span>
    </div>
  </div>
  <div id="jobs-grid" style="padding:10px 40px 28px; display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:12px; max-height:500px; overflow-y:auto;"></div>
</div>

<div style="border-top:1px solid var(--border);padding:8px 40px;background:var(--surface);display:flex;align-items:center;gap:16px;">
  <button onclick="toggleJobsFeed()" id="feed-toggle-btn"
    style="background:transparent;border:1px solid var(--border);color:var(--muted);padding:5px 14px;font-family:var(--mono);font-size:10px;letter-spacing:1px;text-transform:uppercase;cursor:pointer;border-radius:2px;transition:all 0.15s;"
    onmouseover="this.style.borderColor='var(--accent)';this.style.color='var(--accent)'"
    onmouseout="this.style.borderColor='var(--border)';this.style.color='var(--muted)'">
    ⚡ Show Live Jobs
  </button>
  <span style="font-size:10px;color:var(--muted);">Auto-pulls civil engineering jobs from Jobberman &amp; MyJobMag</span>
</div>

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
