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
  document.getElementById('edit-cv-btn').disabled        = false;
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

    // Show candidate meta, hide new-user prompt
    var prompt = document.getElementById('new-user-prompt');
    var cMeta  = document.getElementById('candidate-meta');
    var yMeta  = document.getElementById('years-meta');
    if (prompt) prompt.style.display = 'none';
    if (cMeta)  cMeta.style.display  = 'block';
    if (yMeta)  yMeta.style.display  = 'block';
    window._hasUploadedCV = true;

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
  // Check if this visitor already has a CV in session (returning user / page refresh)
  try {
    var sc = await fetch('/session-check');
    var sd = await sc.json();
    if (sd.has_cv && sd.name) {
      var prompt = document.getElementById('new-user-prompt');
      var cMeta  = document.getElementById('candidate-meta');
      var yMeta  = document.getElementById('years-meta');
      var nameEl = document.getElementById('candidate-name');
      var yrEl   = document.getElementById('candidate-years');
      var hdrBtn = document.getElementById('header-upload-btn');
      var hdrTxt = document.getElementById('header-upload-text');
      if (prompt) prompt.style.display = 'none';
      if (cMeta)  cMeta.style.display  = 'block';
      if (yMeta)  yMeta.style.display  = 'block';
      if (nameEl) nameEl.textContent   = sd.name;
      if (yrEl)   yrEl.textContent     = sd.years;
      if (hdrBtn) hdrBtn.classList.add('loaded');
      if (hdrTxt) hdrTxt.textContent   = '✓ ' + sd.name;
      window._hasUploadedCV = true;
    }
  } catch(e) {}

  // Load tracker badge
  try {
    var res  = await fetch('/tracker/list');
    var data = await res.json();
    _trackerData = Array.isArray(data) ? data : [];
    updateTrackerBadge();
  } catch(e) {}
});

/* ── Batch Apply ──────────────────────────────────────────────────────────── */

var _batchResults = [];

function showBatchApply() {
  var panel   = document.getElementById('batch-panel');
  var overlay = document.getElementById('batch-overlay');
  panel.style.display   = 'flex';
  overlay.style.display = 'block';
  setTimeout(() => panel.style.transform = 'translateX(0)', 10);
}

function hideBatchApply() {
  var panel   = document.getElementById('batch-panel');
  var overlay = document.getElementById('batch-overlay');
  panel.style.transform = 'translateX(100%)';
  setTimeout(() => {
    panel.style.display   = 'none';
    overlay.style.display = 'none';
  }, 260);
}

async function runBatchPreview() {
  var btn        = document.getElementById('batch-scan-btn');
  var loading    = document.getElementById('batch-loading');
  var idle       = document.getElementById('batch-idle');
  var listEl     = document.getElementById('batch-list');
  var loadingMsg = document.getElementById('batch-loading-msg');
  var minScore   = parseInt(document.getElementById('batch-min-score').value);
  var emailOnly  = document.getElementById('batch-email-only').checked;

  btn.disabled      = true;
  btn.textContent   = 'Scanning...';
  idle.style.display    = 'none';
  listEl.style.display  = 'none';
  loading.style.display = 'block';

  var msgs = [
    'Scraping Jobberman & MyJobMag...',
    'Scoring jobs against your CV...',
    'Filtering by match score...',
    'Almost done...'
  ];
  var mi = 0;
  var msgTimer = setInterval(() => {
    loadingMsg.textContent = msgs[Math.min(mi++, msgs.length - 1)];
  }, 4000);

  try {
    var res  = await fetch('/batch-preview', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify({min_confidence: minScore, email_only: emailOnly}),
    });
    var data = await res.json();
    clearInterval(msgTimer);

    if (data.status !== 'ok') {
      loading.style.display = 'none';
      idle.style.display    = 'block';
      idle.innerHTML = '<div style="font-size:24px">⚠️</div><div style="font-size:12px;margin-top:8px;color:#f06060">' + esc(data.message) + '</div>';
      return;
    }

    _batchResults = data.results || [];
    renderBatchResults(data);

  } catch(e) {
    clearInterval(msgTimer);
    loading.style.display = 'none';
    idle.style.display    = 'block';
    idle.innerHTML = '<div style="font-size:24px">⚠️</div><div style="font-size:12px;margin-top:8px;color:#f06060">Network error: ' + esc(e.message) + '</div>';
  } finally {
    btn.disabled    = false;
    btn.textContent = '🔍 Scan Jobs';
    loading.style.display = 'none';
  }
}

function renderBatchResults(data) {
  var listEl  = document.getElementById('batch-list');
  var cards   = document.getElementById('batch-cards');
  var summary = document.getElementById('batch-summary-text');

  listEl.style.display = 'block';

  var emailCount = _batchResults.filter(j => j.can_email).length;
  summary.innerHTML =
    '<b style="color:var(--accent)">' + _batchResults.length + '</b> matches found · ' +
    '<b style="color:var(--accent)">' + emailCount + '</b> can be emailed directly · ' +
    '<span style="color:var(--muted)">' + data.skipped + ' jobs below threshold or filtered out</span>';

  cards.innerHTML = '';

  if (!_batchResults.length) {
    cards.innerHTML = '<div style="text-align:center;padding:40px;color:var(--muted);font-size:12px">No jobs matched your criteria. Try lowering the minimum score.</div>';
    return;
  }

  _batchResults.forEach((job, i) => {
    var card = document.createElement('div');
    card.className  = 'batch-card';
    card.dataset.idx = i;

    var confColor = job.confidence >= 70 ? '#c8f060' : job.confidence >= 55 ? '#f0d060' : '#f08060';
    var methodTag = job.can_email
      ? '<span style="font-size:9px;background:#0d2a1a;color:#4cde80;border:1px solid #1a5c30;padding:2px 7px;border-radius:8px">✉ Email</span>'
      : '<span style="font-size:9px;background:#1a1020;color:#a080f0;border:1px solid #3a2060;padding:2px 7px;border-radius:8px">🔗 Platform</span>';

    card.innerHTML =
      (job.can_email ? '<input type="checkbox" class="batch-checkbox" data-idx="' + i + '" style="accent-color:var(--accent);flex-shrink:0;width:16px;height:16px" onchange="updateBatchCard(this)">' : '<div style="width:16px;flex-shrink:0"></div>') +
      '<div style="flex:1;min-width:0">' +
        '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">' +
          '<span style="font-weight:600;font-size:12px;color:var(--text)">' + esc(job.title) + '</span>' +
          methodTag +
          (job.rank ? '<span style="font-size:9px;color:var(--muted);background:var(--bg);border:1px solid var(--border);padding:2px 6px;border-radius:8px">' + esc(job.rank.replace('_',' ')) + '</span>' : '') +
        '</div>' +
        '<div style="font-size:11px;color:var(--muted);margin-top:2px">' +
          (job.company ? esc(job.company) : '') +
          (job.location ? ' · ' + esc(job.location) : '') +
          (job.salary ? ' · ' + esc(job.salary) : '') +
        '</div>' +
        (job.apply_email ? '<div style="font-size:10px;color:var(--accent);margin-top:3px">→ ' + esc(job.apply_email) + '</div>' : '') +
      '</div>' +
      '<div style="flex-shrink:0;text-align:right">' +
        '<div style="font-size:18px;font-weight:700;color:' + confColor + '">' + job.confidence + '%</div>' +
        '<div class="conf-bar-bg" style="margin-top:4px"><div class="conf-bar-fill" style="width:' + job.confidence + '%;background:' + confColor + '"></div></div>' +
        (job.url ? '<a href="' + esc(job.url) + '" target="_blank" style="font-size:9px;color:var(--muted);text-decoration:none;display:block;margin-top:4px">View →</a>' : '') +
      '</div>';

    cards.appendChild(card);
  });
}

function updateBatchCard(chk) {
  var card = chk.closest('.batch-card');
  if (chk.checked) card.classList.add('selected');
  else card.classList.remove('selected');
}

function batchSelectAll(checked) {
  document.querySelectorAll('.batch-checkbox').forEach(chk => {
    chk.checked = checked;
    updateBatchCard(chk);
  });
}

async function sendBatchSelected() {
  var selected = [];
  document.querySelectorAll('.batch-checkbox:checked').forEach(chk => {
    var idx = parseInt(chk.dataset.idx);
    if (_batchResults[idx]) selected.push(_batchResults[idx]);
  });

  if (!selected.length) {
    alert('No jobs selected. Check the boxes next to jobs you want to apply to.');
    return;
  }

  var emailJobs = selected.filter(j => j.can_email);
  if (!emailJobs.length) {
    alert('None of the selected jobs have an email address. These require applying on the job board directly.');
    return;
  }

  if (!confirm('Send your tailored CV to ' + emailJobs.length + ' employer(s)?\n\n' +
               emailJobs.map(j => '• ' + j.title + (j.company ? ' — ' + j.company : '') + '\n  → ' + j.apply_email).join('\n') +
               '\n\nThis cannot be undone.')) return;

  var btn = document.getElementById('batch-send-btn');
  btn.disabled    = true;
  btn.textContent = 'Sending...';

  try {
    var res  = await fetch('/batch-send', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify({jobs: emailJobs}),
    });
    var data = await res.json();

    if (data.setup_needed) {
      showBatchSmtpHint();
      return;
    }

    var msg = '✓ Sent ' + data.total_sent + ' application(s)!\n\n';
    if (data.sent && data.sent.length)   msg += 'Sent:\n'   + data.sent.map(s => '• ' + s.title + ' → ' + s.to).join('\n');
    if (data.failed && data.failed.length) msg += '\n\nFailed:\n' + data.failed.map(f => '• ' + f.title + ': ' + f.reason).join('\n');
    alert(msg);

    // Update tracker badge
    var res2  = await fetch('/tracker/list');
    var tdata = await res2.json();
    _trackerData = Array.isArray(tdata) ? tdata : [];
    updateTrackerBadge();

    // Uncheck sent jobs
    document.querySelectorAll('.batch-checkbox:checked').forEach(chk => {
      chk.checked = false;
      updateBatchCard(chk);
    });

  } catch(e) {
    alert('Send failed: ' + e.message);
  } finally {
    btn.disabled    = false;
    btn.textContent = '📤 Send Selected';
  }
}

function showBatchSmtpHint() {
  alert('Email not configured yet.\n\nTo enable sending, add these to your Render environment variables:\n\nSMTP_EMAIL = your Gmail address\nSMTP_PASSWORD = your Gmail App Password\n\nGet an App Password at: myaccount.google.com/apppasswords');
}

/* ── CV Editor ────────────────────────────────────────────────────────────── */

var _cvEditorData = { profile: {}, experience: [], education: [], skills: [] };

async function showCvEditor() {
  var panel   = document.getElementById('cv-editor-panel');
  var overlay = document.getElementById('cv-editor-overlay');
  panel.style.display   = 'flex';
  overlay.style.display = 'block';
  setTimeout(() => panel.style.transform = 'translateX(0)', 10);

  // Load current CV data
  try {
    var res  = await fetch('/cv-data');
    var data = await res.json();
    if (data.status === 'ok') {
      _cvEditorData = data;
      populateCvEditor(data);
    }
  } catch(e) {
    console.error('Could not load CV data', e);
  }
}

function hideCvEditor() {
  var panel   = document.getElementById('cv-editor-panel');
  var overlay = document.getElementById('cv-editor-overlay');
  panel.style.transform = 'translateX(100%)';
  setTimeout(() => {
    panel.style.display   = 'none';
    overlay.style.display = 'none';
  }, 260);
}

function switchCvTab(tab, btn) {
  document.querySelectorAll('.cv-tab-pane').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.cv-tab').forEach(b => b.classList.remove('active'));
  document.getElementById('cv-tab-' + tab).style.display = 'block';
  btn.classList.add('active');
}

function populateCvEditor(data) {
  // Profile
  var p = data.profile || {};
  document.getElementById('cvp-name').value     = p.name     || '';
  document.getElementById('cvp-title').value    = p.title    || '';
  document.getElementById('cvp-email').value    = p.email    || '';
  document.getElementById('cvp-phone').value    = p.phone    || '';
  document.getElementById('cvp-location').value = p.location || '';
  document.getElementById('cvp-years').value    = p.experience_years || '';
  document.getElementById('cvp-linkedin').value = p.linkedin || '';

  // Experience
  renderExpList(data.experience || []);

  // Education
  renderEduList(data.education || []);

  // Skills
  document.getElementById('cv-skills-input').value = (data.skills || []).join('\n');
}

/* ── Experience ── */
function renderExpList(expArr) {
  var list = document.getElementById('cv-exp-list');
  list.innerHTML = '';
  expArr.forEach((exp, i) => {
    var card = document.createElement('div');
    card.className   = 'cv-exp-card';
    card.dataset.idx = i;

    var bulletsHtml = (exp.bullets || []).map((b, bi) =>
      '<div class="cv-bullet-row">' +
        '<input class="cv-bullet-input" value="' + esc(b) + '" placeholder="Bullet point..." ' +
               'data-exp="' + i + '" data-bullet="' + bi + '">' +
        '<button onclick="removeBullet(' + i + ',' + bi + ')" title="Remove" ' +
          'style="background:transparent;border:1px solid var(--border);color:var(--muted);' +
          'padding:5px 8px;font-family:var(--mono);font-size:11px;cursor:pointer;border-radius:2px;flex-shrink:0">✕</button>' +
      '</div>'
    ).join('');

    card.innerHTML =
      '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px">' +
        '<div style="font-size:11px;font-weight:600;color:var(--accent)">Experience ' + (i+1) + '</div>' +
        '<button onclick="removeExp(' + i + ')" style="background:transparent;border:1px solid var(--border);' +
          'color:var(--muted);padding:3px 8px;font-family:var(--mono);font-size:10px;cursor:pointer;border-radius:2px">Remove</button>' +
      '</div>' +
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px">' +
        '<div class="cv-field-group"><label class="cv-label">Job Title</label>' +
          '<input class="cv-input" data-exp="' + i + '" data-field="role" value="' + esc(exp.role||'') + '" placeholder="Site Engineer"></div>' +
        '<div class="cv-field-group"><label class="cv-label">Company</label>' +
          '<input class="cv-input" data-exp="' + i + '" data-field="company" value="' + esc(exp.company||'') + '" placeholder="Company name"></div>' +
        '<div class="cv-field-group"><label class="cv-label">Period</label>' +
          '<input class="cv-input" data-exp="' + i + '" data-field="period" value="' + esc(exp.period||'') + '" placeholder="Jan 2020 – Present"></div>' +
        '<div class="cv-field-group"><label class="cv-label">Location</label>' +
          '<input class="cv-input" data-exp="' + i + '" data-field="location" value="' + esc(exp.location||'') + '" placeholder="Lagos, Nigeria"></div>' +
      '</div>' +
      '<div class="cv-label" style="margin-bottom:8px">Key Achievements / Bullets</div>' +
      '<div id="cv-bullets-' + i + '">' + bulletsHtml + '</div>' +
      '<button onclick="addBullet(' + i + ')" ' +
        'style="margin-top:6px;background:transparent;border:1px dashed var(--border);color:var(--muted);' +
        'padding:6px;width:100%;font-family:var(--mono);font-size:10px;cursor:pointer;border-radius:2px">+ Add Bullet</button>';

    list.appendChild(card);
  });
}

function addCvExperience() {
  _cvEditorData.experience.push({ role:'', company:'', period:'', location:'', bullets:[''] });
  renderExpList(_cvEditorData.experience);
}

function removeExp(i) {
  _cvEditorData.experience.splice(i, 1);
  renderExpList(_cvEditorData.experience);
}

function addBullet(expIdx) {
  if (!_cvEditorData.experience[expIdx].bullets) _cvEditorData.experience[expIdx].bullets = [];
  _cvEditorData.experience[expIdx].bullets.push('');
  renderExpList(_cvEditorData.experience);
}

function removeBullet(expIdx, bulletIdx) {
  _cvEditorData.experience[expIdx].bullets.splice(bulletIdx, 1);
  renderExpList(_cvEditorData.experience);
}

/* ── Education ── */
function renderEduList(eduArr) {
  var list = document.getElementById('cv-edu-list');
  list.innerHTML = '';
  eduArr.forEach((edu, i) => {
    var card = document.createElement('div');
    card.className   = 'cv-edu-card';
    card.dataset.idx = i;
    card.innerHTML =
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">' +
        '<div style="font-size:11px;font-weight:600;color:var(--accent)">Education ' + (i+1) + '</div>' +
        '<button onclick="removeEdu(' + i + ')" style="background:transparent;border:1px solid var(--border);' +
          'color:var(--muted);padding:3px 8px;font-family:var(--mono);font-size:10px;cursor:pointer;border-radius:2px">Remove</button>' +
      '</div>' +
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">' +
        '<div class="cv-field-group" style="grid-column:1/-1"><label class="cv-label">Degree / Qualification</label>' +
          '<input class="cv-input" data-edu="' + i + '" data-field="degree" value="' + esc(edu.degree||'') + '" placeholder="B.Eng Civil Engineering"></div>' +
        '<div class="cv-field-group" style="grid-column:1/-1"><label class="cv-label">Institution</label>' +
          '<input class="cv-input" data-edu="' + i + '" data-field="institution" value="' + esc(edu.institution||'') + '" placeholder="University of Lagos"></div>' +
        '<div class="cv-field-group"><label class="cv-label">Year</label>' +
          '<input class="cv-input" data-edu="' + i + '" data-field="year" value="' + esc(edu.year||'') + '" placeholder="2015"></div>' +
      '</div>';
    list.appendChild(card);
  });
}

function addCvEducation() {
  _cvEditorData.education.push({ degree:'', institution:'', year:'' });
  renderEduList(_cvEditorData.education);
}

function removeEdu(i) {
  _cvEditorData.education.splice(i, 1);
  renderEduList(_cvEditorData.education);
}

/* ── Save ── */
async function saveCvEditor() {
  var btn = document.getElementById('cv-save-btn');
  btn.textContent = 'Saving...';
  btn.disabled    = true;

  // Collect profile
  var profile = {
    name:             document.getElementById('cvp-name').value.trim(),
    title:            document.getElementById('cvp-title').value.trim(),
    email:            document.getElementById('cvp-email').value.trim(),
    phone:            document.getElementById('cvp-phone').value.trim(),
    location:         document.getElementById('cvp-location').value.trim(),
    experience_years: parseInt(document.getElementById('cvp-years').value) || 0,
    linkedin:         document.getElementById('cvp-linkedin').value.trim(),
  };

  // Collect experience (read from DOM inputs)
  var experience = [];
  document.querySelectorAll('.cv-exp-card').forEach(card => {
    var i    = parseInt(card.dataset.idx);
    var exp  = { role:'', company:'', period:'', location:'', bullets:[] };
    card.querySelectorAll('input[data-field]').forEach(inp => { exp[inp.dataset.field] = inp.value.trim(); });
    card.querySelectorAll('.cv-bullet-input').forEach(inp => {
      if (inp.value.trim()) exp.bullets.push(inp.value.trim());
    });
    experience.push(exp);
  });

  // Collect education
  var education = [];
  document.querySelectorAll('.cv-edu-card').forEach(card => {
    var edu = { degree:'', institution:'', year:'' };
    card.querySelectorAll('input[data-field]').forEach(inp => { edu[inp.dataset.field] = inp.value.trim(); });
    education.push(edu);
  });

  // Collect skills
  var skills = document.getElementById('cv-skills-input').value
    .split('\n').map(s => s.trim()).filter(Boolean);

  // Update local cache
  _cvEditorData = { profile, experience, education, skills };

  try {
    var res  = await fetch('/cv-save', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify({ profile, experience, education, skills }),
    });
    var data = await res.json();

    if (data.status === 'ok') {
      btn.textContent = '✓ Saved!';
      btn.style.background = '#2d6a2d';
      var ind = document.getElementById('cv-save-indicator');
      ind.style.display = 'block';
      setTimeout(() => {
        btn.textContent      = '💾 Save Changes';
        btn.style.background = '';
        btn.disabled         = false;
        ind.style.display    = 'none';
      }, 2500);
    } else {
      btn.textContent = 'Save Changes';
      btn.disabled    = false;
      alert('Save failed: ' + data.message);
    }
  } catch(e) {
    btn.textContent = 'Save Changes';
    btn.disabled    = false;
    alert('Network error: ' + e.message);
  }
}

/* ── Welcome Overlay ──────────────────────────────────────────────────────── */

window.addEventListener('load', function() {
  if (typeof FIRST_VISIT !== 'undefined' && FIRST_VISIT === true) {
    var overlay = document.getElementById('welcome-overlay');
    if (overlay) overlay.style.display = 'flex';
  }
});

function skipWelcome() {
  var overlay = document.getElementById('welcome-overlay');
  if (overlay) overlay.style.display = 'none';
}

async function welcomeUpload(input) {
  var status = document.getElementById('welcome-upload-status');
  if (!input.files || !input.files[0]) return;

  var file = input.files[0];
  if (file.type !== 'application/pdf') {
    status.textContent = '⚠ Please upload a PDF file';
    status.style.color = '#f06060';
    return;
  }

  status.textContent  = '⏳ Uploading and reading your CV...';
  status.style.color  = 'var(--muted)';

  var formData = new FormData();
  formData.append('cv_file', file);

  try {
    var res  = await fetch('/upload-cv', { method: 'POST', body: formData });
    var data = await res.json();

    if (data.status === 'ok') {
      status.textContent = '✓ CV uploaded — welcome, ' + (data.name || 'engineer') + '!';
      status.style.color = 'var(--accent)';

      // Update main header with real name/years
      if (data.name)  document.getElementById('candidate-name').textContent  = data.name;
      if (data.years) document.getElementById('candidate-years').textContent = data.years;

      // Update main upload zone to confirmed state
      var uploadZone = document.getElementById('upload-zone');
      var confirmed  = document.getElementById('cv-confirmed');
      var nameEl     = document.getElementById('cv-name-display');
      if (uploadZone) uploadZone.classList.add('confirmed');
      if (confirmed)  confirmed.classList.add('visible');
      if (nameEl)     nameEl.textContent = file.name;

      // Store session_id for /process fallback
      if (data.session_id) window._sessionId = data.session_id;

      // Close overlay after short delay
      setTimeout(() => {
        var overlay = document.getElementById('welcome-overlay');
        if (overlay) {
          overlay.style.opacity = '0';
          overlay.style.transition = 'opacity 0.4s';
          setTimeout(() => overlay.style.display = 'none', 400);
        }
      }, 1200);

    } else {
      status.textContent = '⚠ ' + (data.message || 'Upload failed');
      status.style.color = '#f06060';
    }
  } catch(e) {
    status.textContent = '⚠ Upload failed — ' + e.message;
    status.style.color = '#f06060';
  }
}

/* ── Client-side Event Tracking ──────────────────────────────────────────── */

function track(event, meta) {
  fetch('/track', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({event, meta: meta || {}})
  }).catch(() => {});
}

// Track page load
track('page_view');

/* ── Auth ─────────────────────────────────────────────────────────────────── */

var _currentUser = null;

// Check login state on load
window.addEventListener('load', async function() {
  try {
    var res  = await fetch('/account/me');
    var data = await res.json();
    if (data.logged_in) {
      _currentUser = data;
      updateAuthNav(data);
    }
  } catch(e) {}
});

function showAuth() {
  if (_currentUser) {
    // Already logged in — show logout option
    if (confirm('Signed in as ' + _currentUser.email + '\n\nSign out?')) doLogout();
    return;
  }
  var overlay = document.getElementById('auth-overlay');
  overlay.style.display = 'flex';
  setTimeout(() => document.getElementById('auth-login-email').focus(), 100);
  track('auth_modal_open');
}

function hideAuth() {
  document.getElementById('auth-overlay').style.display = 'none';
}

function switchAuthTab(tab) {
  document.getElementById('auth-login-form').style.display    = tab === 'login'    ? 'block' : 'none';
  document.getElementById('auth-register-form').style.display = tab === 'register' ? 'block' : 'none';
  document.getElementById('auth-tab-login').classList.toggle('active',    tab === 'login');
  document.getElementById('auth-tab-register').classList.toggle('active', tab === 'register');
}

function updateAuthNav(user) {
  var display = document.getElementById('auth-user-display');
  var btn     = document.getElementById('auth-nav-btn');
  if (user) {
    display.textContent = user.name || user.email;
    display.style.display = 'block';
    btn.textContent = '👤 Account';
  } else {
    display.style.display = 'none';
    btn.textContent = '👤 Sign In';
  }
}

async function doLogin() {
  var email    = document.getElementById('auth-login-email').value.trim();
  var password = document.getElementById('auth-login-password').value;
  var errEl    = document.getElementById('auth-login-error');
  var btn      = document.getElementById('auth-login-btn');

  if (!email || !password) { errEl.textContent = 'Email and password required'; errEl.style.display='block'; return; }
  btn.textContent = 'Signing in...'; btn.disabled = true;
  errEl.style.display = 'none';

  try {
    var res  = await fetch('/auth/login', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({email, password})
    });
    var data = await res.json();
    if (data.status === 'ok') {
      _currentUser = data;
      updateAuthNav(data);
      hideAuth();
      track('login');
      showToast('Welcome back, ' + (data.name || data.email) + '!');
    } else {
      errEl.textContent = data.message;
      errEl.style.display = 'block';
    }
  } catch(e) {
    errEl.textContent = 'Network error. Try again.';
    errEl.style.display = 'block';
  } finally {
    btn.textContent = 'Sign In'; btn.disabled = false;
  }
}

async function doRegister() {
  var name     = document.getElementById('auth-reg-name').value.trim();
  var email    = document.getElementById('auth-reg-email').value.trim();
  var password = document.getElementById('auth-reg-password').value;
  var errEl    = document.getElementById('auth-reg-error');
  var btn      = document.getElementById('auth-reg-btn');

  if (!email || !password) { errEl.textContent = 'Email and password required'; errEl.style.display='block'; return; }
  if (password.length < 8)  { errEl.textContent = 'Password must be at least 8 characters'; errEl.style.display='block'; return; }
  btn.textContent = 'Creating account...'; btn.disabled = true;
  errEl.style.display = 'none';

  try {
    var res  = await fetch('/auth/register', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({name, email, password})
    });
    var data = await res.json();
    if (data.status === 'ok') {
      _currentUser = data;
      updateAuthNav(data);
      hideAuth();
      track('register');
      showToast('Account created! Welcome, ' + (data.name || data.email) + ' 🎉');
    } else {
      errEl.textContent = data.message;
      errEl.style.display = 'block';
    }
  } catch(e) {
    errEl.textContent = 'Network error. Try again.';
    errEl.style.display = 'block';
  } finally {
    btn.textContent = 'Create Account'; btn.disabled = false;
  }
}

async function doLogout() {
  await fetch('/auth/logout', {method:'POST'});
  _currentUser = null;
  updateAuthNav(null);
  track('logout');
  showToast('Signed out.');
}

/* ── Toast notification ───────────────────────────────────────────────────── */

function showToast(msg, duration) {
  var t = document.getElementById('toast-notif');
  if (!t) {
    t = document.createElement('div');
    t.id = 'toast-notif';
    t.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);' +
      'background:var(--surface);border:1px solid var(--accent);color:var(--accent);' +
      'padding:10px 20px;font-family:var(--mono);font-size:12px;border-radius:3px;' +
      'z-index:600;opacity:0;transition:opacity 0.25s;pointer-events:none;white-space:nowrap';
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.style.opacity = '1';
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.style.opacity = '0', duration || 3000);
}

/* ── Feedback bar ─────────────────────────────────────────────────────────── */

function showFeedbackBar() {
  var bar = document.getElementById('feedback-bar');
  bar.style.display = 'flex';
}

function hideFeedbackBar() {
  document.getElementById('feedback-bar').style.display = 'none';
}

async function sendFeedback(rating, btnEl) {
  var msg      = document.getElementById('feedback-msg').value.trim();
  var finalRating = rating === -1 ? 1 : rating;  // -1 = enter key on comment = thumbs up

  if (btnEl) {
    // Highlight selected button
    document.querySelectorAll('#feedback-bar button').forEach(b => b.style.background = '');
    btnEl.style.background = rating === 1 ? '#0d2a1a' : '#2a0d0d';
  }

  try {
    await fetch('/feedback', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({rating: finalRating, message: msg, context: 'post_generate'})
    });
    hideFeedbackBar();
    showToast(finalRating === 1 ? 'Thanks! Glad it helped 👍' : 'Thanks for the feedback. We\'ll improve it.');
  } catch(e) {}
}

// Show feedback bar 4 seconds after CV download
var _origDownloadCV = window.downloadCV;
if (typeof downloadCV === 'function') {
  window.downloadCV = async function() {
    if (typeof _origDownloadCV === 'function') await _origDownloadCV();
    setTimeout(showFeedbackBar, 4000);
    track('cv_download_click');
  };
}
