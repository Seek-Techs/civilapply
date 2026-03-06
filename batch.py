# batch.py — Process multiple job descriptions at once
#
# HOW TO USE:
# 1. Create a folder called 'jobs' in your project root
# 2. Save each job description as a .txt file inside it
#    e.g. jobs/rovedana.txt, jobs/ldd.txt, jobs/oasis.txt
# 3. Run: python batch.py
# 4. Results saved to: output/batch_results/
#    - ranked_summary.txt   → ranked list, apply to these first
#    - rovedana.txt         → CV summary + cover letter for that job
#    - ldd.txt              → CV summary + cover letter for that job
#    - etc.
#
# WHY BATCH MODE?
# Processing jobs one at a time costs 3-4 minutes each.
# Batch processes all of them overnight or while you eat.
# You wake up to ranked, ready-to-send applications.

import sys, os, json, copy, time

ROOT = os.path.dirname(os.path.abspath(__file__))
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
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and v and k not in os.environ:
                os.environ[k] = v

_load_env()

from civil_engineering.job_parser                        import parse_job_description
from civil_engineering.normalization.normalize_cv        import normalize_cv
from civil_engineering.intelligence.builder              import build_intelligence
from civil_engineering.cv_adapter.adapter                import adapt_cv
from civil_engineering.cover_letter.cover_letter_builder import build_cover_letter
from civil_engineering.cv_tailor                         import ai_rewrite_cv, generate_cv_summary
from civil_engineering.cv_pdf                            import generate_cv_pdf
from civil_engineering.scoring.job_ranker                import rank_job
from civil_engineering.decision_explainer                import explain_decisions
from civil_engineering.eligibility.job_filter            import is_job_relevant

CV_PATH = os.path.join(ROOT, 'civil_engineering', 'data', 'cv.json')
with open(CV_PATH) as f:
    BASE_CV = normalize_cv(json.load(f))

JOBS_DIR   = os.path.join(ROOT, 'jobs')
OUTPUT_DIR = os.path.join(ROOT, 'output', 'batch_results')

RANK_LABELS = {
    'strong_fit':    '✅  APPLY FIRST',
    'strategic_fit': '⚠️   APPLY — manage expectations',
    'rejected':      '❌  SKIP',
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _bar(confidence: int, width: int = 20) -> str:
    filled = int(confidence / 100 * width)
    return '█' * filled + '░' * (width - filled)

def _process_one(filename: str, raw_text: str) -> dict:
    """Run the full pipeline on one job description. Returns a result dict."""
    job      = parse_job_description(raw_text)
    job_dict = job.to_dict()

    ok, reason = is_job_relevant(BASE_CV, job_dict, raw_text=raw_text)
    if not ok:
        return {
            'file':       filename,
            'status':     'rejected',
            'reason':     reason,
            'title':      job.title or 'Unknown',
            'confidence': 0,
            'rank':       'rejected',
            'salary':     job.salary or '',
            'email':      job.apply_email or '',
        }

    cv           = copy.deepcopy(BASE_CV)
    intelligence = build_intelligence(cv, job_dict)
    decisions    = explain_decisions(cv, job_dict, intelligence)
    conf_block   = next((d for d in decisions if d.get('type') == 'confidence_score'), {})
    confidence   = conf_block.get('overall_confidence', 0)
    ranking      = rank_job(confidence)
    adapted_cv   = adapt_cv(cv, job_dict, intelligence)

    tailor     = ai_rewrite_cv(adapted_cv, job_dict, intelligence)
    cv_summary = tailor.get('summary') or generate_cv_summary(adapted_cv, job_dict)
    provider   = tailor.get('provider', 'rule-based').upper()

    cover_letter = build_cover_letter(
        profile      = cv['profile'],
        job          = job_dict,
        intelligence = intelligence,
        cv           = adapted_cv,
        ai_summary   = cv_summary,
    )

    return {
        'file':         filename,
        'status':       'ok',
        'title':        job.title or 'Unknown',
        'salary':       job.salary or 'Not specified',
        'email':        job.apply_email or '',
        'years':        job.years_required,
        'projects':     ', '.join(job.project_types),
        'confidence':   confidence,
        'rank':         ranking['rank'],
        'seniority':    intelligence.get('seniority', '').replace('_', ' ').title(),
        'alignment':    intelligence.get('project_alignment', {}).get('strength', '').title(),
        'cv_summary':   cv_summary,
        'cover_letter': cover_letter,
        'provider':     provider,
    }

def _write_application(result: dict, out_path: str):
    """Write application txt file and a tailored CV PDF alongside it."""
    sep   = '─' * 60
    lines = [
        f"APPLICATION: {result['title']}",
        f"File       : {result['file']}",
        f"Salary     : {result['salary']}",
        f"Apply to   : {result['email'] or 'See job description'}",
        f"Confidence : {result['confidence']}/100  {_bar(result['confidence'])}",
        f"Verdict    : {RANK_LABELS.get(result['rank'], result['rank'])}",
        '',
        sep,
        f"CV SUMMARY  [{result['provider']}]",
        sep,
        '',
        result['cv_summary'],
        '',
        '↑ Paste into the Profile/Summary section of your CV',
        '',
        sep,
        'COVER LETTER',
        sep,
        '',
        result['cover_letter'],
        '',
        '↑ Paste into your email body. Attach your CV. Send.',
        '',
    ]
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    # Generate matching CV PDF in same folder
    try:
        pdf_path = out_path.replace('.txt', '_cv.pdf')
        generate_cv_pdf(BASE_CV, pdf_path, cv_summary=result.get('cv_summary', ''))
    except Exception:
        pass  # PDF failure never stops batch run

def _write_summary(results: list, out_path: str):
    """Write the ranked summary file."""
    name  = BASE_CV['profile']['name']
    sep   = '═' * 70
    lines = [
        sep,
        f"  BATCH RESULTS — {name}",
        f"  {len(results)} jobs processed",
        sep,
        '',
    ]

    apply_first = [r for r in results if r['rank'] == 'strong_fit']
    apply_also  = [r for r in results if r['rank'] == 'strategic_fit']
    skip        = [r for r in results if r['rank'] == 'rejected']

    sections = [
        ('✅  APPLY FIRST', apply_first),
        ('⚠️   CONSIDER APPLYING', apply_also),
        ('❌  REJECTED — WRONG INDUSTRY OR TOO WEAK', skip),
    ]

    for heading, group in sections:
        if not group:
            continue
        lines += [f'  {heading}', '  ' + '─' * 50]
        for r in group:
            email_str  = f"  → {r['email']}" if r['email'] else ''
            salary_str = f"  {r['salary']}" if r['salary'] and r['salary'] != 'Not specified' else ''
            conf_bar   = _bar(r['confidence'], 15)
            if r['status'] == 'rejected':
                lines.append(f"  {r['file']:25}  {r['title']:30}  REJECTED")
                lines.append(f"    Reason: {r.get('reason','')[:65]}")
            else:
                lines.append(f"  {r['file']:25}  {r['title']:30}  {r['confidence']:3}/100  {conf_bar}")
                if salary_str:
                    lines.append(f"    Salary  : {r['salary']}")
                if email_str:
                    lines.append(f"    Apply to: {r['email']}")
                lines.append(f"    Output  : output/batch_results/{r['file']}")
            lines.append('')
        lines.append('')

    lines += [
        sep,
        '  HOW TO APPLY',
        '  ─────────────',
        '  1. Open the output file for each job in the APPLY FIRST list',
        '  2. Copy the CV Summary → paste into your CV Profile section',
        '  3. Copy the Cover Letter → open Yahoo Mail → Compose',
        '  4. Paste letter into body, attach your CV, send',
        sep,
    ]

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    # Generate matching CV PDF in same folder
    try:
        pdf_path = out_path.replace('.txt', '_cv.pdf')
        generate_cv_pdf(BASE_CV, pdf_path, cv_summary=result.get('cv_summary', ''))
    except Exception:
        pass  # PDF failure never stops batch run

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print()
    print('═' * 60)
    print('  CIVIL APPLY — BATCH MODE')
    print('═' * 60)

    # ── Find job files ─────────────────────────────────────────────────────
    if not os.path.exists(JOBS_DIR):
        os.makedirs(JOBS_DIR)
        print(f'''
  No jobs folder found. Created: {JOBS_DIR}

  HOW TO USE:
  1. Save each job description as a .txt file in the jobs/ folder
     Example: jobs/rovedana.txt
              jobs/ldd_consulting.txt
              jobs/oasis.txt
  2. Run: python batch.py
''')
        return

    job_files = sorted([
        f for f in os.listdir(JOBS_DIR)
        if f.endswith('.txt') and not f.startswith('_')
    ])

    if not job_files:
        print(f'\n  No .txt files found in {JOBS_DIR}')
        print('  Save job descriptions as .txt files and try again.\n')
        return

    print(f'\n  Candidate : {BASE_CV["profile"]["name"]}')
    print(f'  Jobs found: {len(job_files)}')
    print(f'  Output    : output/batch_results/')
    print()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── Process each job ───────────────────────────────────────────────────
    results = []
    for i, filename in enumerate(job_files, 1):
        filepath = os.path.join(JOBS_DIR, filename)
        with open(filepath, encoding='utf-8', errors='replace') as f:
            raw_text = f.read().strip()

        if not raw_text:
            print(f'  [{i}/{len(job_files)}] {filename:30} EMPTY — skipped')
            continue

        print(f'  [{i}/{len(job_files)}] {filename:30} processing...', end='', flush=True)

        try:
            result = _process_one(filename, raw_text)
            results.append(result)

            conf  = result['confidence']
            rank  = result['rank']
            mark  = '✅' if rank == 'strong_fit' else '⚠️ ' if rank == 'strategic_fit' else '❌'
            print(f' {mark} {conf}/100 — {result["title"]}')

            # Write individual application file
            if result['status'] == 'ok':
                out_path = os.path.join(OUTPUT_DIR, filename)
                _write_application(result, out_path)

        except Exception as e:
            print(f' ERROR: {e}')
            results.append({'file': filename, 'status': 'error', 'confidence': 0,
                            'rank': 'rejected', 'title': 'Error', 'reason': str(e),
                            'salary': '', 'email': ''})

        # Small pause between AI calls to avoid rate limiting
        if i < len(job_files):
            time.sleep(1)

    # ── Sort and write summary ─────────────────────────────────────────────
    results.sort(key=lambda r: -r['confidence'])

    summary_path = os.path.join(OUTPUT_DIR, '_ranked_summary.txt')
    _write_summary(results, summary_path)

    # ── Print final ranking ────────────────────────────────────────────────
    print()
    print('─' * 60)
    print('  RESULTS — RANKED BY CONFIDENCE')
    print('─' * 60)
    for i, r in enumerate(results, 1):
        mark = '✅' if r['rank'] == 'strong_fit' else '⚠️ ' if r['rank'] == 'strategic_fit' else '❌'
        email = f"  {r['email']}" if r['email'] else ''
        print(f"  {i}. {mark} {r['confidence']:3}/100  {r['title']:30} {email}")

    apply_count = sum(1 for r in results if r['rank'] in ('strong_fit', 'strategic_fit'))
    print()
    print(f'  {apply_count} jobs to apply for out of {len(results)} processed')
    print(f'  Full details: output/batch_results/_ranked_summary.txt')
    print('═' * 60)
    print()

if __name__ == '__main__':
    main()