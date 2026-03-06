/* CivilApply — app.js  */

/* ── Generate ──────────────────────────────────────────────────────────────── */

async function generate() {
  var jd = document.getElementById('jd-input').value.trim();
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

/* ── Render result ─────────────────────────────────────────────────────────── */

function renderResult(data) {
  document.getElementById('result').classList.add('visible');

  var rejSec     = document.getElementById('rejected-section');
  var parsedSec  = document.getElementById('parsed-section');
  var matchSec   = document.getElementById('match-section');
  var summarySec = document.getElementById('summary-section');
  var letterSec  = document.getElementById('letter-section');

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
    'strong_fit':    ['apply',   '✅', 'Apply Confidently'],
    'strategic_fit': ['caution', '⚠️',  'Apply — manage expectations'],
    'rejected':      ['skip',    '❌', 'Do Not Apply'],
  };
  var vdata = verdictMap[m.rank] || ['skip', '❌', 'Do Not Apply'];
  document.getElementById('verdict-box').innerHTML =
    '<div class="verdict ' + vdata[0] + '">' + vdata[1] + ' ' + vdata[2] + '</div>';

  var riskHtml = (m.risk_flags || []).map(function(f) {
    return '<div class="match-pill" style="border-color:#f06050;color:#f06050">' + f + '</div>';
  }).join('');
  document.getElementById('match-details').innerHTML =
    '<div class="match-pill">Seniority <span>' + m.seniority + '</span></div>' +
    '<div class="match-pill">Project match <span>' + m.alignment + '</span></div>' +
    riskHtml;

  document.getElementById('cv-summary-text').textContent  = data.cv_summary;
  document.getElementById('provider-tag').textContent     = data.provider;
  document.getElementById('cover-letter-text').textContent = data.cover_letter;
  document.getElementById('download-cv-btn').disabled     = false;
  document.getElementById('output-panel').scrollTop       = 0;

  // Show apply bar using info collected during "Use This Job"
  showApplyBar(
    window._currentApplyEmail,
    window._currentApplyMethod,
    window._currentJobUrl,
    window._currentJobTitle,
    data.cover_letter,
    data.cv_summary
  );
}

function showError(msg) {
  var box = document.getElementById('error-box');
  box.textContent = '⚠ ' + msg;
  box.style.display = 'block';
  document.getElementById('placeholder').style.display = 'flex';
}

/* ── Upload CV ─────────────────────────────────────────────────────────────── */

async function uploadCV(input) {
  var file = input.files[0];
  if (!file) return;
  console.log('[uploadCV] file:', file.name);

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
      lbl.textContent = '⚠ ' + data.message;
      return;
    }

    if (data.session_id) {
      window._cvSessionId = data.session_id;
    }

    var hdrBtn  = document.getElementById('header-upload-btn');
    var hdrText = document.getElementById('header-upload-text');
    if (hdrBtn && !hdrBtn.classList.contains('loaded')) hdrBtn.classList.add('loaded');
    if (hdrText) hdrText.textContent = data.name ? ('✓ ' + data.name) : '✓ CV Uploaded';

    var nameStrong = document.getElementById('candidate-name');
    if (nameStrong && data.name) nameStrong.textContent = data.name;

    var yearsEl = document.getElementById('candidate-years');
    if (yearsEl && data.years !== undefined) yearsEl.textContent = data.years;

    if (zone && !zone.classList.contains('has-cv')) zone.classList.add('has-cv');
    var skills = (data.skills || []).slice(0, 3).join(', ') || 'uploaded';
    if (lbl)     lbl.textContent = (data.exp_count || 0) + ' roles · ' + skills;
    if (confirm && !confirm.classList.contains('visible')) confirm.classList.add('visible');
    if (nameEl)  nameEl.textContent = (data.name || '') + '  ·  ' + (data.years || 0) + ' yrs';

    if (data.warning) {
      var errBox = document.getElementById('error-box');
      errBox.textContent = '⚠ ' + data.warning;
      errBox.style.display = 'block';
      errBox.style.borderColor = '#f0a500';
      errBox.style.color = '#f0a500';
    }
  } catch(e) {
    console.log('[uploadCV] error:', e);
    if (lbl) lbl.textContent = '⚠ Upload failed: ' + e.message;
  }
}

/* ── Download CV PDF ───────────────────────────────────────────────────────── */

async function downloadCV() {
  var btn     = document.getElementById('download-cv-btn');
  var summary = document.getElementById('cv-summary-text').textContent;
  var title   = document.getElementById('p-title').textContent;
  btn.disabled = true;
  btn.textContent = '⬇ Generating PDF...';
  try {
    var res = await fetch('/download-cv', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({cv_summary: summary, job_title: title,
                            session_id: window._cvSessionId || null}),
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
    btn.textContent = '✓ Downloaded';
    setTimeout(function() { btn.disabled = false; btn.textContent = '⬇ Download Tailored CV PDF'; }, 3000);
  } catch(e) {
    btn.textContent = '⬇ Download Tailored CV PDF';
    btn.disabled = false;
  }
}

/* ── Copy helpers ──────────────────────────────────────────────────────────── */

function copyEmailDetails() {
  var row     = document.getElementById('p-email-row');
  var email   = row.dataset.email || '';
  var subject = row.dataset.subject || '';
  navigator.clipboard.writeText('To: ' + email + '\nSubject: ' + subject).then(function() {
    var btn = document.getElementById('copy-details-btn');
    btn.textContent = 'Copied!';
    setTimeout(function() { btn.textContent = 'Copy Address'; }, 2000);
  });
}

function copyText(id, btn) {
  navigator.clipboard.writeText(document.getElementById(id).textContent).then(function() {
    btn.textContent = 'Copied!';
    setTimeout(function() { btn.textContent = 'Copy'; }, 2000);
  });
}

/* ── Jobs Feed ─────────────────────────────────────────────────────────────── */

var _jobsFeedOpen = false;

function toggleJobsFeed() {
  _jobsFeedOpen = !_jobsFeedOpen;
  var panel = document.getElementById('jobs-panel');
  var btn   = document.getElementById('feed-toggle-btn');
  panel.style.display = _jobsFeedOpen ? 'block' : 'none';
  btn.textContent = _jobsFeedOpen ? '⚡ Hide Jobs Feed' : '⚡ Show Live Jobs';
  if (_jobsFeedOpen && document.getElementById('jobs-grid').children.length === 0) {
    loadJobs();
  }
}

async function loadJobs(forceRefresh) {
  var status  = document.getElementById('jobs-status');
  var grid    = document.getElementById('jobs-grid');
  var refreshBtn = document.getElementById('refresh-jobs-btn');

  status.textContent = forceRefresh ? 'Scraping live...' : 'Loading...';
  if (refreshBtn) { refreshBtn.disabled = true; refreshBtn.textContent = 'Scraping...'; }
  grid.innerHTML = '<div style="color:#888880;font-size:12px;padding:20px 0;">Scraping Jobberman &amp; MyJobMag with headless browser — takes ~60s on first load, instant from cache...</div>';

  var sources = [];
  if (document.getElementById('src-jobberman').checked) sources.push('jobberman');
  if (document.getElementById('src-myjobmag').checked)  sources.push('myjobmag');

  try {
    var res = await fetch('/scrape-jobs', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({sources: sources, max_pages: 2, force_refresh: !!forceRefresh}),
    });
    var data = await res.json();

    if (data.status === 'error') {
      var errMsg = data.message || 'Unknown error';
      var installHint = data.install_needed
        ? '<div style="margin-top:10px;padding:10px;background:#1a1200;border:1px solid #f0a500;border-radius:3px;font-size:11px;color:#f0a500;">'
          + 'To enable job scraping, run in terminal:<br>'
          + '<code style="color:#c8f060;">pip install playwright</code><br>'
          + '<code style="color:#c8f060;">python -m playwright install chromium</code>'
          + '</div>'
        : '';
      grid.innerHTML = '<div style="color:#f06050;font-size:12px;padding:10px 0;">' + errMsg + installHint + '</div>';
      status.textContent = 'Failed';
      if (refreshBtn) { refreshBtn.disabled = false; refreshBtn.textContent = 'Refresh Jobs'; }
      return;
    }

    var cacheNote = data.cached ? ' (cached)' : ' (live)';
    status.textContent = data.count + ' jobs' + cacheNote;
    renderJobs(data.jobs || []);
  } catch(e) {
    grid.innerHTML = '<div style="color:#f06050;font-size:12px;padding:20px 0;">Network error: ' + e.message + '</div>';
    status.textContent = 'Error';
  } finally {
    if (refreshBtn) { refreshBtn.disabled = false; refreshBtn.textContent = 'Refresh Jobs'; }
  }
}

function renderJobs(jobs) {
  var grid = document.getElementById('jobs-grid');
  if (!jobs.length) {
    grid.innerHTML = '<div style="color:#888880;font-size:12px;padding:20px;">No civil engineering jobs found. Try refreshing.</div>';
    return;
  }

  var html = '';
  for (var i = 0; i < jobs.length; i++) {
    var j = jobs[i];
    var sourceColor = j.source === 'Jobberman' ? '#c8f060' : '#60c8f0';
    var salaryHtml  = j.salary ? '<div style="color:#f0a030;font-size:11px;margin-top:4px;">' + esc(j.salary) + '</div>' : '';
    var companyHtml = j.company ? '<div style="font-size:11px;color:#888880;">' + esc(j.company) + '</div>' : '';
    var snippetHtml = j.snippet ? '<div style="font-size:10px;color:#888880;margin-top:6px;line-height:1.5;">' + esc(j.snippet.slice(0, 120)) + '...</div>' : '';

    html += '<div style="background:#0e0f0c;border:1px solid #2a2b27;border-radius:3px;padding:14px;">';
    html += '<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:6px;">';
    html += '<div style="font-size:12px;font-weight:500;color:#e8e8e2;line-height:1.4;">' + esc(j.title) + '</div>';
    html += '<span style="font-size:9px;letter-spacing:1px;text-transform:uppercase;color:' + sourceColor + ';white-space:nowrap;border:1px solid ' + sourceColor + ';padding:1px 6px;border-radius:2px;">' + esc(j.source) + '</span>';
    html += '</div>';
    html += companyHtml;
    html += '<div style="font-size:10px;color:#888880;margin-top:2px;">' + esc(j.location) + ' &nbsp;·&nbsp; ' + esc(j.posted) + '</div>';
    html += salaryHtml;
    html += snippetHtml;
    html += '<div style="display:flex;gap:8px;margin-top:10px;">';
    html += '<button onclick="useJob(' + i + ', this)" style="background:#c8f060;color:#0e0f0c;border:none;padding:4px 12px;font-family:inherit;font-size:10px;cursor:pointer;border-radius:2px;min-width:90px;">Use This Job</button>';
    html += '<a href="' + esc(j.url) + '" target="_blank" rel="noopener" style="background:transparent;border:1px solid #2a2b27;color:#888880;padding:4px 12px;font-size:10px;cursor:pointer;border-radius:2px;text-decoration:none;">View</a>';
    html += '</div></div>';
  }
  grid.innerHTML = html;

  // Store jobs globally so useJob() can access them by index
  window._scrapedJobs = jobs;
}

// Store the current job's apply info for use after Generate
window._currentApplyEmail  = null;
window._currentApplyMethod = null;
window._currentJobUrl      = null;
window._currentJobTitle    = null;

async function useJob(idx, btnEl) {
  var jobs = window._scrapedJobs || [];
  var j    = jobs[idx];
  if (!j) return;
  var jdInput = document.getElementById('jd-input');

  // Clear any previous apply state
  window._currentApplyEmail  = null;
  window._currentApplyMethod = null;
  window._currentJobUrl      = j.url;
  window._currentJobTitle    = j.title;
  _hideApplyBar();

  // Show loading state immediately
  var preview = j.title + (j.company ? ' (' + j.company + ')' : '');
  if (j.salary)   preview += '\nSalary: ' + j.salary;
  if (j.location) preview += '\nLocation: ' + j.location;
  preview += '\n\nLoading full job description...';
  jdInput.value = preview;
  window.scrollTo({top: 0, behavior: 'smooth'});

  if (btnEl) { btnEl.disabled = true; btnEl.textContent = 'Loading...'; }

  try {
    var res  = await fetch('/fetch-job-detail', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url: j.url}),
    });
    var data = await res.json();

    if (data.status === 'ok' && data.description) {
      var full = j.title + (j.company ? ' — ' + j.company : '') + '\n';
      if (j.location) full += 'Location: ' + j.location + '\n';
      if (j.salary)   full += 'Salary: '   + j.salary   + '\n';
      full += '\n' + data.description;
      jdInput.value = full;

      // Store apply info for after Generate
      window._currentApplyEmail  = data.apply_email  || null;
      window._currentApplyMethod = data.apply_method || 'platform';
    } else {
      window.open(j.url, '_blank');
      var fallback = j.title + (j.company ? ' — ' + j.company : '') + '\n';
      if (j.location) fallback += 'Location: ' + j.location + '\n';
      if (j.salary)   fallback += 'Salary: '   + j.salary   + '\n';
      fallback += '\n[Job page opened in new tab — copy the full description and paste it here, then click Generate]';
      jdInput.value = fallback;
      window._currentApplyMethod = 'platform';
    }
  } catch(e) {
    var fallback = j.title + '\n';
    if (j.snippet) fallback += '\n' + j.snippet;
    jdInput.value = fallback;
  } finally {
    if (btnEl) { btnEl.disabled = false; btnEl.textContent = 'Use This Job'; }
    jdInput.focus();
  }
}

/* ── Apply Bar ─────────────────────────────────────────────────────────────── */

function _hideApplyBar() {
  var bar = document.getElementById('apply-bar');
  if (bar) bar.style.display = 'none';
}

function showApplyBar(applyEmail, applyMethod, jobUrl, jobTitle, coverLetter, cvSummary) {
  // Called after Generate completes
  var bar = document.getElementById('apply-bar');
  if (!bar) return;

  var emailSection   = document.getElementById('apply-email-section');
  var platformSection = document.getElementById('apply-platform-section');
  var emailAddr      = document.getElementById('apply-email-addr');
  var subjectInp     = document.getElementById('apply-subject');
  var bodyArea       = document.getElementById('apply-body');
  var platformLink   = document.getElementById('apply-platform-link');

  bar.style.display = 'block';

  if (applyEmail && applyMethod === 'email') {
    emailSection.style.display    = 'block';
    platformSection.style.display = 'none';
    emailAddr.textContent = applyEmail;
    subjectInp.value = 'Application for ' + (jobTitle || 'the advertised role');
    bodyArea.value   = coverLetter || '';
    // Store for send
    bar.dataset.toEmail   = applyEmail;
    bar.dataset.cvSummary = cvSummary || '';
    bar.dataset.jobTitle  = (jobTitle || '').replace(/\s+/g, '_');
  } else {
    emailSection.style.display    = 'none';
    platformSection.style.display = 'block';
    if (platformLink) {
      platformLink.href        = jobUrl || '#';
      platformLink.textContent = 'Apply on ' + (jobUrl && jobUrl.includes('jobberman') ? 'Jobberman' :
                                  jobUrl && jobUrl.includes('linkedin') ? 'LinkedIn' :
                                  jobUrl && jobUrl.includes('myjobmag') ? 'MyJobMag' : 'Job Board') + ' →';
      var _jTitle = jobTitle, _jUrl = jobUrl;
      platformLink.onclick = function() {
        addToTracker({
          title:    _jTitle || 'Unknown role',
          url:      _jUrl || '',
          platform: _jUrl && _jUrl.includes('jobberman') ? 'Jobberman' :
                    _jUrl && _jUrl.includes('myjobmag')  ? 'MyJobMag'  :
                    _jUrl && _jUrl.includes('linkedin')  ? 'LinkedIn'  : 'Platform',
          method:   'Platform (Easy Apply)',
          status:   'Applied',
        });
      };
    }
  }
}

async function sendApplication() {
  var bar      = document.getElementById('apply-bar');
  var btn      = document.getElementById('send-app-btn');
  var subject  = document.getElementById('apply-subject').value.trim();
  var body     = document.getElementById('apply-body').value.trim();
  var toEmail  = bar.dataset.toEmail;
  var cvSummary = bar.dataset.cvSummary;
  var jobTitle  = bar.dataset.jobTitle;

  if (!toEmail) { alert('No recipient email address found.'); return; }
  if (!body)    { alert('Please write a cover letter before sending.'); return; }

  btn.disabled    = true;
  btn.textContent = 'Sending...';

  try {
    var res  = await fetch('/send-application', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify({ to_email: toEmail, subject, body, cv_summary: cvSummary, job_title: jobTitle }),
    });
    var data = await res.json();

    if (data.status === 'ok') {
      btn.textContent = '✓ Sent!';
      btn.style.background = '#2d6a2d';
      // Auto-log to tracker
      addToTracker({
        title:    window._currentJobTitle || bar.dataset.jobTitle || 'Unknown role',
        company:  '',
        location: '',
        salary:   '',
        url:      window._currentJobUrl || '',
        platform: window._currentJobUrl && window._currentJobUrl.includes('jobberman') ? 'Jobberman' :
                  window._currentJobUrl && window._currentJobUrl.includes('myjobmag')  ? 'MyJobMag'  : '',
        method:   'Email',
        status:   'Applied',
      });
      setTimeout(() => { btn.textContent = 'Send Application'; btn.style.background = ''; btn.disabled = false; }, 3000);
    } else if (data.setup_needed) {
      btn.disabled    = false;
      btn.textContent = 'Send Application';
      showSmtpSetupHint();
    } else {
      btn.disabled    = false;
      btn.textContent = 'Send Application';
      alert('Send failed: ' + data.message);
    }
  } catch(e) {
    btn.disabled    = false;
    btn.textContent = 'Send Application';
    alert('Network error: ' + e.message);
  }
}

function showSmtpSetupHint() {
  var hint = document.getElementById('smtp-setup-hint');
  if (hint) hint.style.display = 'block';
}

function copyApplyEmail() {
  var addr = document.getElementById('apply-email-addr').textContent;
  navigator.clipboard.writeText(addr).then(() => {
    var btn = document.getElementById('copy-apply-email-btn');
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = 'Copy', 1500);
  });
}

function esc(s) {
  if (!s) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ── Keyboard shortcut ─────────────────────────────────────────────────────── */

document.addEventListener('keydown', function(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') generate();
});

/* ── Application Tracker ──────────────────────────────────────────────────── */

var _trackerFilter = 'All';
var _trackerData   = [];

function showTracker() {
  var panel   = document.getElementById('tracker-panel');
  var overlay = document.getElementById('tracker-overlay');
  panel.style.display   = 'flex';
  overlay.style.display = 'block';
  setTimeout(() => panel.style.transform = 'translateX(0)', 10);
  loadTracker();
}

function hideTracker() {
  var panel   = document.getElementById('tracker-panel');
  var overlay = document.getElementById('tracker-overlay');
  panel.style.transform = 'translateX(100%)';
  setTimeout(() => {
    panel.style.display   = 'none';
    overlay.style.display = 'none';
  }, 260);
}

async function loadTracker() {
  document.getElementById('tracker-loading').style.display = 'block';
  document.getElementById('tracker-empty').style.display   = 'none';
  try {
    var res  = await fetch('/tracker/list');
    var data = await res.json();
    _trackerData = Array.isArray(data) ? data : [];
    renderTracker();
    updateTrackerBadge();
  } catch(e) {
    document.getElementById('tracker-loading').textContent = 'Failed to load. Is the server running?';
  }
}

function filterTracker(status, btn) {
  _trackerFilter = status;
  document.querySelectorAll('.tracker-filter-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  renderTracker();
}

function renderTracker() {
  var list    = document.getElementById('tracker-list');
  var loading = document.getElementById('tracker-loading');
  var empty   = document.getElementById('tracker-empty');
  loading.style.display = 'none';

  var items = _trackerFilter === 'All'
    ? _trackerData
    : _trackerData.filter(a => a.status === _trackerFilter);

  // Update stats
  var counts = {};
  _trackerData.forEach(a => { counts[a.status] = (counts[a.status]||0) + 1; });
  var statsEl = document.getElementById('tracker-stats');
  statsEl.innerHTML = Object.entries(counts).map(([s,n]) =>
    '<span class="status-pill status-' + s + '" style="margin:1px 2px">' + n + ' ' + s + '</span>'
  ).join('') || '<span style="color:var(--muted)">No applications yet</span>';

  // Remove old cards
  list.querySelectorAll('.tracker-card').forEach(c => c.remove());

  if (!items.length) {
    empty.style.display = 'block';
    return;
  }
  empty.style.display = 'none';

  items.forEach(app => {
    var card = document.createElement('div');
    card.className = 'tracker-card';
    card.dataset.id = app.id;

    var date = app.applied_at ? app.applied_at.split(' ')[0] : '—';
    var urlHtml = app.url
      ? '<a href="' + esc(app.url) + '" target="_blank" rel="noopener" style="color:var(--accent);font-size:10px;text-decoration:none">View Job →</a>'
      : '';
    var methodTag = app.method
      ? '<span style="font-size:9px;color:var(--muted);background:var(--bg);border:1px solid var(--border);padding:1px 6px;border-radius:8px">' + esc(app.method) + '</span>'
      : '';

    card.innerHTML =
      '<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;flex-wrap:wrap">' +
        '<div style="flex:1;min-width:0">' +
          '<div style="font-weight:600;font-size:13px;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + esc(app.title) + '</div>' +
          '<div style="font-size:11px;color:var(--muted);margin-top:2px">' +
            (app.company ? esc(app.company) : '') +
            (app.location ? ' · ' + esc(app.location) : '') +
            (app.salary   ? ' · ' + esc(app.salary) : '') +
          '</div>' +
          '<div style="margin-top:6px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">' +
            '<span class="status-pill status-' + esc(app.status) + '">' + esc(app.status) + '</span>' +
            methodTag + urlHtml +
            '<span style="font-size:10px;color:var(--muted)">' + date + '</span>' +
          '</div>' +
        '</div>' +
        '<div style="display:flex;gap:6px;align-items:center;flex-shrink:0">' +
          '<select onchange="updateTrackerField(' + app.id + ', \'status\', this.value)" ' +
            'style="background:var(--bg);border:1px solid var(--border);color:var(--text);' +
            'padding:4px 6px;font-family:var(--mono);font-size:10px;border-radius:2px;cursor:pointer">' +
            ['Applied','Interview','Offer','Rejected','Withdrawn'].map(s =>
              '<option value="' + s + '"' + (s === app.status ? ' selected' : '') + '>' + s + '</option>'
            ).join('') +
          '</select>' +
          '<button onclick="deleteTrackerEntry(' + app.id + ')" title="Delete" ' +
            'style="background:transparent;border:1px solid var(--border);color:var(--muted);' +
            'padding:4px 8px;font-family:var(--mono);font-size:11px;cursor:pointer;border-radius:2px">✕</button>' +
        '</div>' +
      '</div>' +
      '<div style="margin-top:8px">' +
        '<input value="' + esc(app.notes||'') + '" placeholder="Add notes (e.g. interviewer name, next steps)..." ' +
          'onblur="updateTrackerField(' + app.id + ', \'notes\', this.value)" ' +
          'style="width:100%;box-sizing:border-box;background:var(--bg);border:1px solid transparent;' +
          'color:var(--muted);padding:5px 8px;font-family:var(--mono);font-size:11px;border-radius:2px;outline:none;' +
          'transition:border-color 0.15s" ' +
          'onfocus="this.style.borderColor=\'var(--border)\';this.style.color=\'var(--text)\'" ' +
          'onblur="this.style.borderColor=\'transparent\';this.style.color=\'var(--muted)\';updateTrackerField(' + app.id + ',\'notes\',this.value)">' +
      '</div>';

    list.appendChild(card);
  });
}

async function updateTrackerField(id, field, value) {
  try {
    await fetch('/tracker/update', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify({id, field, value}),
    });
    // Update local data
    var entry = _trackerData.find(a => a.id === id);
    if (entry) entry[field] = value;
    if (field === 'status') { renderTracker(); updateTrackerBadge(); }
  } catch(e) { console.error('Tracker update failed', e); }
}

async function deleteTrackerEntry(id) {
  if (!confirm('Remove this application from your tracker?')) return;
  try {
    await fetch('/tracker/delete', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify({id}),
    });
    _trackerData = _trackerData.filter(a => a.id !== id);
    renderTracker();
    updateTrackerBadge();
  } catch(e) { alert('Delete failed: ' + e.message); }
}

async function addToTracker(jobData) {
  try {
    await fetch('/tracker/add', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify(jobData),
    });
    // Refresh badge count
    var res  = await fetch('/tracker/list');
    var data = await res.json();
    _trackerData = Array.isArray(data) ? data : [];
    updateTrackerBadge();
  } catch(e) { console.error('Tracker add failed', e); }
}

async function manualAddApplication() {
  var title   = document.getElementById('manual-title').value.trim();
  var company = document.getElementById('manual-company').value.trim();
  var url     = document.getElementById('manual-url').value.trim();
  if (!title) { document.getElementById('manual-title').focus(); return; }
  await addToTracker({title, company, url, method: 'Manual', status: 'Applied'});
  document.getElementById('manual-title').value   = '';
  document.getElementById('manual-company').value = '';
  document.getElementById('manual-url').value     = '';
  loadTracker();  // Refresh the list
}

function updateTrackerBadge() {
  var badge = document.getElementById('tracker-count-badge');
  var n     = _trackerData.length;
  if (n > 0) {
    badge.textContent  = n;
    badge.style.display = 'inline';
  } else {
    badge.style.display = 'none';
  }
}

// Load badge count on page load
window.addEventListener('load', async () => {
  try {
    var res  = await fetch('/tracker/list');
    var data = await res.json();
    _trackerData = Array.isArray(data) ? data : [];
    updateTrackerBadge();
  } catch(e) {}
});
