"""
patch_webpy.py — Run this ONCE to fix the JavaScript in web.py.

Usage: python patch_webpy.py

It finds the <script> block in your web.py and replaces it with
a clean version that has no backtick syntax errors.
"""

import os, sys, shutil, re

HERE   = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, 'web.py')

if not os.path.exists(TARGET):
    print(f"ERROR: web.py not found at {TARGET}")
    sys.exit(1)

content = open(TARGET, encoding='utf-8').read()

# ── Check current state ───────────────────────────────────────────────────────
js_start = content.find('<script>')
js_end   = content.find('</script>')
if js_start == -1 or js_end == -1:
    print("ERROR: Could not find <script> block in web.py")
    sys.exit(1)

old_js = content[js_start + len('<script>'):js_end]
bt_count = old_js.count('`')
print(f"Current web.py: {len(content)} bytes, {bt_count} backticks in JS")

# ── Back up ───────────────────────────────────────────────────────────────────
backup = TARGET + '.bak'
shutil.copy(TARGET, backup)
print(f"Backed up to web.py.bak")

# ── New clean JS — zero backticks, pure ES5 compatible ────────────────────────
NEW_JS = r"""
async function generate() {
  const jd = document.getElementById('jd-input').value.trim();
  if (!jd) return;

  var btn     = document.getElementById('gen-btn');
  var spinner = document.getElementById('spinner');
  var label   = document.getElementById('btn-label');
  btn.disabled = true;
  spinner.style.display = 'block';
  label.textContent = 'Analysing...';
  document.getElementById('error-box').style.display = 'none';
  document.getElementById('placeholder').style.display = 'none';
  document.getElementById('result').classList.remove('visible');

  console.log('[generate] session_id:', window._cvSessionId);

  try {
    var res = await fetch('/process', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({job_description: jd, session_id: window._cvSessionId || null}),
    });
    var data = await res.json();
    if (data.status === 'error') { showError(data.message); return; }
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
  var result = document.getElementById('result');
  result.classList.add('visible');

  var rejSec      = document.getElementById('rejected-section');
  var parsedSec   = document.getElementById('parsed-section');
  var matchSec    = document.getElementById('match-section');
  var summarySec  = document.getElementById('summary-section');
  var letterSec   = document.getElementById('letter-section');

  if (data.status === 'rejected') {
    rejSec.style.display = 'block';
    document.getElementById('rejected-reason').textContent = data.reason;
    parsedSec.style.display = matchSec.style.display =
      summarySec.style.display = letterSec.style.display = 'none';
    return;
  }

  rejSec.style.display = 'none';
  parsedSec.style.display = matchSec.style.display =
    summarySec.style.display = letterSec.style.display = '';

  var j = data.job;
  document.getElementById('p-title').textContent    = j.title;
  document.getElementById('p-years').textContent    = j.years || 'Not specified';
  document.getElementById('p-projects').textContent = j.projects || 'Not detected';
  document.getElementById('p-salary').textContent   = j.salary || 'Not specified';

  if (j.email) {
    document.getElementById('p-email-row').style.display = '';
    document.getElementById('p-email-text').textContent  = j.email;
    document.getElementById('p-email-subject').textContent = 'Application for ' + j.title;
    document.getElementById('p-email-row').dataset.email   = j.email;
    document.getElementById('p-email-row').dataset.subject = 'Application for ' + j.title;
  }
  if (j.skills) {
    document.getElementById('p-skills-row').style.display = '';
    document.getElementById('p-skills').textContent = j.skills;
  }

  var m    = data.match;
  var conf = m.confidence;
  var cls  = conf >= 70 ? '' : conf >= 50 ? 'medium' : 'low';

  var confNum = document.getElementById('conf-number');
  confNum.textContent = conf;
  confNum.className   = 'conf-number ' + cls;

  var bar = document.getElementById('conf-bar');
  bar.className = 'conf-bar ' + cls;
  setTimeout(function() { bar.style.width = conf + '%'; }, 50);

  var verdictMap = {
    'strong_fit':    ['apply',   '&#10003;', 'Apply Confidently'],
    'strategic_fit': ['caution', '&#9888;',  'Apply - manage expectations'],
    'rejected':      ['skip',    '&#10007;', 'Do Not Apply'],
  };
  var vdata = verdictMap[m.rank] || ['skip', '&#10007;', 'Do Not Apply'];
  document.getElementById('verdict-box').innerHTML =
    '<div class="verdict ' + vdata[0] + '">' + vdata[1] + ' ' + vdata[2] + '</div>';

  var riskHtml = (m.risk_flags || []).map(function(f) {
    return '<div class="match-pill" style="border-color:#f06050;color:#f06050">' + f + '</div>';
  }).join('');
  document.getElementById('match-details').innerHTML =
    '<div class="match-pill">Seniority <span>' + m.seniority + '</span></div>' +
    '<div class="match-pill">Project match <span>' + m.alignment + '</span></div>' +
    riskHtml;

  document.getElementById('cv-summary-text').textContent = data.cv_summary;
  document.getElementById('provider-tag').textContent    = data.provider;
  document.getElementById('cover-letter-text').textContent = data.cover_letter;
  document.getElementById('download-cv-btn').disabled = false;
  document.getElementById('output-panel').scrollTop = 0;
}

function showError(msg) {
  var box = document.getElementById('error-box');
  box.textContent = 'Warning: ' + msg;
  box.style.display = 'block';
  document.getElementById('placeholder').style.display = 'flex';
}

async function uploadCV(input) {
  console.log('[uploadCV] triggered, file:', input.files[0] ? input.files[0].name : 'none');
  var file = input.files[0];
  if (!file) return;

  var zone    = document.getElementById('upload-zone');
  var lbl     = document.getElementById('upload-label-text');
  var confirm = document.getElementById('cv-confirmed');
  var nameEl  = document.getElementById('cv-name-display');

  lbl.textContent = 'Uploading...';

  var formData = new FormData();
  formData.append('cv_file', file);

  try {
    var res  = await fetch('/upload-cv', {method: 'POST', body: formData});
    var data = await res.json();
    console.log('[uploadCV] response:', data);

    if (data.status === 'error') {
      lbl.textContent = 'Error: ' + data.message;
      return;
    }

    if (data.session_id) {
      window._cvSessionId = data.session_id;
      console.log('[uploadCV] session stored:', data.session_id);
    }

    var hdrBtn  = document.getElementById('header-upload-btn');
    var hdrText = document.getElementById('header-upload-text');
    if (hdrBtn)  hdrBtn.className = hdrBtn.className + ' loaded';
    if (hdrText) hdrText.textContent = data.name ? ('OK: ' + data.name) : 'CV Uploaded';

    var nameStrong = document.getElementById('candidate-name');
    if (nameStrong && data.name) nameStrong.textContent = data.name;

    if (zone)    zone.className = zone.className + ' has-cv';
    var skills = (data.skills || []).slice(0,3).join(', ') || 'uploaded';
    if (lbl)     lbl.textContent = (data.exp_count || 0) + ' roles - ' + skills;
    if (confirm) confirm.className = confirm.className + ' visible';
    if (nameEl)  nameEl.textContent = (data.name || '') + '  ' + (data.years || 0) + ' yrs';

    if (data.warning) {
      var errBox = document.getElementById('error-box');
      errBox.textContent = 'Warning: ' + data.warning;
      errBox.style.display = 'block';
      errBox.style.borderColor = '#f0a500';
      errBox.style.color = '#f0a500';
    }

  } catch(e) {
    console.log('[uploadCV] error:', e);
    if (lbl) lbl.textContent = 'Upload failed: ' + e.message;
  }
}

async function downloadCV() {
  var btn     = document.getElementById('download-cv-btn');
  var summary = document.getElementById('cv-summary-text').textContent;
  var title   = document.getElementById('p-title').textContent;
  btn.disabled = true;
  btn.textContent = 'Generating PDF...';
  try {
    var res = await fetch('/download-cv', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({cv_summary: summary, job_title: title}),
    });
    if (!res.ok) throw new Error('Server error');
    var blob = await res.blob();
    var url  = URL.createObjectURL(blob);
    var a    = document.createElement('a');
    a.href = url;
    a.download = 'CV_' + title.replace(/ /g, '_') + '.pdf';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    btn.textContent = 'Downloaded';
    setTimeout(function() { btn.disabled = false; btn.textContent = 'Download Tailored CV PDF'; }, 3000);
  } catch(e) {
    btn.textContent = 'Download Tailored CV PDF';
    btn.disabled = false;
  }
}

function copyEmailDetails() {
  var row     = document.getElementById('p-email-row');
  var email   = row.dataset.email || '';
  var subject = row.dataset.subject || '';
  var text    = 'To: ' + email + '\nSubject: ' + subject;
  navigator.clipboard.writeText(text).then(function() {
    var btn = document.getElementById('copy-details-btn');
    btn.textContent = 'Copied!';
    setTimeout(function() { btn.textContent = 'Copy Address'; }, 2000);
  });
}

function copyText(id, btn) {
  var text = document.getElementById(id).textContent;
  navigator.clipboard.writeText(text).then(function() {
    btn.textContent = 'Copied!';
    setTimeout(function() { btn.textContent = 'Copy'; }, 2000);
  });
}

document.addEventListener('keydown', function(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') generate();
});
"""

# ── Patch the file ────────────────────────────────────────────────────────────
before = content[:js_start + len('<script>')]
after  = content[js_end:]
new_content = before + NEW_JS + after

# Verify no backticks in new JS
if '`' in NEW_JS:
    print("ERROR: New JS still has backticks!")
    sys.exit(1)

open(TARGET, 'w', encoding='utf-8').write(new_content)
print("Patched successfully!")
print(f"New file: {len(new_content)} bytes")
print(f"Backticks in new JS: {NEW_JS.count(chr(96))}")
print()
print("Now restart the server:  python web.py")