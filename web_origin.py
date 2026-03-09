# web.py — Civil Engineering Job Application Web Interface
# Run: python web.py
# Open: http://localhost:5000

import sys, os, copy, json, traceback

ROOT = os.path.dirname(os.path.abspath(__file__))
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
from civil_engineering.scoring.job_ranker                import rank_job
from civil_engineering.decision_explainer                import explain_decisions
from civil_engineering.eligibility.job_filter            import is_job_relevant

CV_PATH = os.path.join(ROOT, 'civil_engineering', 'data', 'cv.json')

with open(CV_PATH) as f:
    BASE_CV = normalize_cv(json.load(f))

app = Flask(__name__)

# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_pipeline(raw_text: str) -> dict:
    job      = parse_job_description(raw_text)
    job_dict = job.to_dict()

    is_relevant, reason = is_job_relevant(BASE_CV, job_dict, raw_text=raw_text)
    if not is_relevant:
        return {'status': 'rejected', 'reason': reason, 'job': {
            'title': job.title, 'salary': job.salary,
        }}

    cv           = copy.deepcopy(BASE_CV)
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
        profile      = cv['profile'],
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
            'seniority':   intelligence.get('seniority', 'unknown').replace('_', ' ').title(),
            'alignment':   intelligence.get('project_alignment', {}).get('strength', 'none').title(),
            'risk_flags':  [f.replace('_', ' ') for f in intelligence.get('risk_flags', [])],
        },
        'cv_summary':    cv_summary,
        'provider':      provider.upper(),
        'cover_letter':  cover_letter,
    }

# ── Routes ─────────────────────────────────────────────────────────────────────

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

@app.route('/process', methods=['POST'])
def process():
    data = request.get_json()
    raw_text = (data or {}).get('job_description', '').strip()
    if not raw_text:
        return jsonify({'status': 'error', 'message': 'No job description provided'})
    try:
        result = run_pipeline(raw_text)
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e), 'trace': traceback.format_exc()})

# ── HTML Template ──────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Civil Apply — {{ name }}</title>
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

  /* ── Layout ── */
  .workspace {
    display: grid;
    grid-template-columns: 1fr 1fr;
    height: calc(100vh - 65px);
  }

  /* ── Input Panel ── */
  .input-panel {
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    padding: 32px 36px;
    gap: 16px;
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
    padding: 32px 36px;
    gap: 24px;
  }

  .placeholder-msg {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex: 1;
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
    <div class="meta-item">Candidate: <strong>{{ name }}</strong></div>
    <div class="meta-item">Experience: <strong>{{ years }} yrs</strong></div>
    <div class="provider-badge">{{ provider }}</div>
  </div>
</header>

<div class="workspace">

  <!-- ── Input Panel ── -->
  <div class="input-panel">
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
            <div class="parsed-item" id="p-email-row" style="display:none">
              <div class="parsed-key">Apply To</div>
              <div class="parsed-val">
                <a class="email-val" id="p-email" href="#"></a>
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
            ↑ Paste into your email or application form
          </div>
        </div>
      </div>

    </div><!-- /result -->
  </div><!-- /output-panel -->
</div><!-- /workspace -->

<script>
async function generate() {
  const jd = document.getElementById('jd-input').value.trim();
  if (!jd) return;

  // Loading state
  const btn    = document.getElementById('gen-btn');
  const spinner = document.getElementById('spinner');
  const label  = document.getElementById('btn-label');
  btn.disabled = true;
  spinner.style.display = 'block';
  label.textContent = 'Analysing...';
  document.getElementById('error-box').style.display = 'none';
  document.getElementById('placeholder').style.display = 'none';
  document.getElementById('result').classList.remove('visible');

  try {
    const res  = await fetch('/process', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({job_description: jd}),
    });
    const data = await res.json();

    if (data.status === 'error') {
      showError(data.message);
      return;
    }

    renderResult(data);

  } catch(e) {
    showError('Network error: ' + e.message);
  } finally {
    btn.disabled = false;
    spinner.style.display = 'none';
    label.textContent = 'Generate Application';
  }
}

function renderResult(data) {
  const result = document.getElementById('result');
  result.classList.add('visible');

  // ── Rejected ──────────────────────────────────────────────────────────────
  const rejSec = document.getElementById('rejected-section');
  const parsedSec  = document.getElementById('parsed-section');
  const matchSec   = document.getElementById('match-section');
  const summarySec = document.getElementById('summary-section');
  const letterSec  = document.getElementById('letter-section');

  if (data.status === 'rejected') {
    rejSec.style.display = 'block';
    document.getElementById('rejected-reason').textContent = data.reason;
    parsedSec.style.display = 'none';
    matchSec.style.display  = 'none';
    summarySec.style.display = 'none';
    letterSec.style.display  = 'none';
    return;
  }

  rejSec.style.display = 'none';
  parsedSec.style.display = matchSec.style.display =
    summarySec.style.display = letterSec.style.display = '';

  // ── Parsed Job ────────────────────────────────────────────────────────────
  const j = data.job;
  document.getElementById('p-title').textContent    = j.title;
  document.getElementById('p-years').textContent    = j.years || 'Not specified';
  document.getElementById('p-projects').textContent = j.projects || 'Not detected';
  document.getElementById('p-salary').textContent   = j.salary || 'Not specified';

  if (j.email) {
    const emailRow = document.getElementById('p-email-row');
    const emailEl  = document.getElementById('p-email');
    emailRow.style.display = '';
    emailEl.textContent = j.email;
    emailEl.href = 'mailto:' + j.email;
  }
  if (j.skills) {
    document.getElementById('p-skills-row').style.display = '';
    document.getElementById('p-skills').textContent = j.skills;
  }

  // ── Match Analysis ────────────────────────────────────────────────────────
  const m    = data.match;
  const conf = m.confidence;
  const cls  = conf >= 70 ? '' : conf >= 50 ? 'medium' : 'low';

  const confNum = document.getElementById('conf-number');
  confNum.textContent = conf;
  confNum.className   = 'conf-number ' + cls;

  const bar = document.getElementById('conf-bar');
  bar.className = 'conf-bar ' + cls;
  setTimeout(() => bar.style.width = conf + '%', 50);

  const verdictMap = {
    'strong_fit':   ['apply',   '✅', 'Apply Confidently'],
    'strategic_fit':['caution', '⚠️', 'Apply — manage expectations'],
    'rejected':     ['skip',    '❌', 'Do Not Apply'],
  };
  const [vcls, vicon, vtxt] = verdictMap[m.rank] || ['skip','❌','Do Not Apply'];
  document.getElementById('verdict-box').innerHTML =
    `<div class="verdict ${vcls}">${vicon} ${vtxt}</div>`;

  const details = document.getElementById('match-details');
  details.innerHTML = `
    <div class="match-pill">Seniority <span>${m.seniority}</span></div>
    <div class="match-pill">Project match <span>${m.alignment}</span></div>
    ${m.risk_flags.map(f=>`<div class="match-pill" style="border-color:#f06050;color:#f06050">${f}</div>`).join('')}
  `;

  // ── CV Summary ────────────────────────────────────────────────────────────
  document.getElementById('cv-summary-text').textContent = data.cv_summary;
  document.getElementById('provider-tag').textContent    = data.provider;

  // ── Cover Letter ──────────────────────────────────────────────────────────
  document.getElementById('cover-letter-text').textContent = data.cover_letter;

  // Scroll to top of output
  document.getElementById('output-panel').scrollTop = 0;
}

function showError(msg) {
  const box = document.getElementById('error-box');
  box.textContent = '⚠ ' + msg;
  box.style.display = 'block';
  document.getElementById('placeholder').style.display = 'flex';
}

function copyText(id, btn) {
  const text = document.getElementById(id).textContent;
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = 'Copied!';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.textContent = 'Copy';
      btn.classList.remove('copied');
    }, 2000);
  });
}

// Allow Ctrl+Enter to generate
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') generate();
});
</script>
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
    app.run(debug=False, port=5000)