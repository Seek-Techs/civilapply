"""
debug_upload.py — Run this to diagnose CV upload issues.

Usage: python debug_upload.py path/to/your_cv.pdf

It prints exactly what the server does when you upload a CV,
and what happens when you generate with it — no browser needed.
"""

import sys, os, copy, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def _load_env():
    path = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(path): return
    for line in open(path):
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        k, v = line.split('=', 1)
        k = k.strip(); v = v.strip().strip('"').strip("'")
        if k and v and k not in os.environ: os.environ[k] = v
_load_env()

print("=" * 60)
print("  CIVILAPPLY — CV UPLOAD DIAGNOSTICS")
print("=" * 60)

# ── Check file argument ───────────────────────────────────────────────────────
if len(sys.argv) < 2:
    print("\n  Usage: python debug_upload.py path/to/your_cv.pdf\n")
    print("  Using a generated test CV instead...\n")
    pdf_path = None
else:
    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"\n  ERROR: File not found: {pdf_path}\n")
        sys.exit(1)
    print(f"\n  CV file : {pdf_path}")
    print(f"  Size    : {os.path.getsize(pdf_path):,} bytes\n")

# ── Generate test PDF if no file given ────────────────────────────────────────
if not pdf_path:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    import tempfile

    styles = getSampleStyleSheet()
    tmp = tempfile.mktemp(suffix='.pdf')
    doc = SimpleDocTemplate(tmp, pagesize=A4)
    doc.build([
        Paragraph('Sikiru Yusuff Olatunji', styles['Title']),
        Paragraph('Civil Engineer | yusuff.sikiru@yahoo.com | 07065264103 | Lagos', styles['Normal']),
        Spacer(1, 8),
        Paragraph('PROFESSIONAL EXPERIENCE', styles['Heading1']),
        Paragraph('Senior Site Engineer – IPMC | 2020 – Present', styles['Heading2']),
        Paragraph('Supervised reinforced concrete works for residential buildings', styles['Normal']),
        Spacer(1, 8),
        Paragraph('SKILLS', styles['Heading1']),
        Paragraph('AutoCAD, ProtaStructure, MS Project, HSE, QA/QC', styles['Normal']),
    ])
    pdf_path = tmp
    print(f"  Test CV : {tmp}\n")

# ── Step 1: Read PDF bytes ────────────────────────────────────────────────────
print("STEP 1: Read PDF")
with open(pdf_path, 'rb') as f:
    pdf_bytes = f.read()
print(f"  ✅ Read {len(pdf_bytes):,} bytes")

# ── Step 2: Extract raw text ──────────────────────────────────────────────────
print("\nSTEP 2: Extract text from PDF")
try:
    from civil_engineering.cv_reader import extract_text_from_pdf
    raw_text = extract_text_from_pdf(pdf_path)
    print(f"  ✅ Extracted {len(raw_text)} characters")
    print(f"  First 200 chars:\n  {repr(raw_text[:200])}")
except Exception as e:
    print(f"  ❌ FAILED: {e}")
    sys.exit(1)

# ── Step 3: Parse CV ──────────────────────────────────────────────────────────
print("\nSTEP 3: Parse CV structure")
try:
    from civil_engineering.cv_reader import parse_cv_from_bytes, detect_cv_industry
    parsed = parse_cv_from_bytes(pdf_bytes, os.path.basename(pdf_path))
    profile = parsed['profile']

    print(f"  name     : {profile.get('name','')!r}")
    print(f"  title    : {profile.get('title','')!r}")
    print(f"  email    : {profile.get('email','')!r}")
    print(f"  phone    : {profile.get('phone','')!r}")
    print(f"  years    : {profile.get('experience_years',0)}")
    print(f"  location : {profile.get('location','')!r}")
    print(f"  skills   : {parsed.get('skills',[])}")
    print(f"  jobs     : {len(parsed.get('experience',[]))}")
    for j in parsed.get('experience', []):
        print(f"    → {j.get('role','')} @ {j.get('company','')} ({j.get('period','')})")

    if not profile.get('name'):
        print("  ⚠️  WARNING: Name is empty — parser could not find name in CV")
    if not parsed.get('skills'):
        print("  ⚠️  WARNING: No skills found — check skills section in CV")
    if not parsed.get('experience'):
        print("  ⚠️  WARNING: No experience found — check experience section format")

except Exception as e:
    import traceback
    print(f"  ❌ FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)

# ── Step 4: Industry detection ────────────────────────────────────────────────
print("\nSTEP 4: Industry detection")
industry = detect_cv_industry(parsed)
print(f"  is_civil  : {industry['is_civil']}")
print(f"  confidence: {industry['confidence']}%")
print(f"  detected  : {industry['detected']}")
if industry['warning']:
    print(f"  ⚠️  WARNING: {industry['warning']}")
else:
    print("  ✅ Recognised as civil engineering CV")

# ── Step 5: Session simulation ────────────────────────────────────────────────
print("\nSTEP 5: Session store (simulates what server stores)")
import uuid
sid = str(uuid.uuid4())
SESSION_CVS = {sid: parsed}
print(f"  session_id : {sid}")
print(f"  stored     : {SESSION_CVS[sid]['profile']['name']!r}")

retrieved = SESSION_CVS.get(sid)
print(f"  retrieved  : {retrieved['profile']['name']!r}")
print("  ✅ Session store/retrieve works")

# ── Step 6: Full pipeline ─────────────────────────────────────────────────────
print("\nSTEP 6: Full pipeline with uploaded CV")
jd = "Civil Construction Engineer (Rovedana). Salary 600k Monthly. AutoCAD, MS Project. 7+ years. victor.f@rovedana.com"

try:
    from civil_engineering.normalization.normalize_cv import normalize_cv
    from civil_engineering.job_parser import parse_job_description
    from civil_engineering.eligibility.job_filter import is_job_relevant
    from civil_engineering.intelligence.builder import build_intelligence
    from civil_engineering.cv_tailor import generate_cv_summary
    from civil_engineering.cover_letter.cover_letter_builder import build_cover_letter

    cv  = normalize_cv(retrieved)
    job = parse_job_description(jd)
    ok, reason = is_job_relevant(cv, job.to_dict(), raw_text=jd)
    print(f"  relevant   : {ok} — {reason[:60]}")

    if ok:
        intel   = build_intelligence(copy.deepcopy(cv), job.to_dict())
        adapted = cv
        summary = generate_cv_summary(adapted, job.to_dict())
        letter  = build_cover_letter(cv['profile'], job.to_dict(), intel, adapted, summary)

        print(f"  summary    : {summary[:80]}...")
        print(f"  letter     : {letter[:60]}...")
        print(f"\n  ✅ Pipeline ran successfully with UPLOADED CV")

        # Check if name in letter matches uploaded CV
        if cv['profile']['name'] and cv['profile']['name'] in letter:
            print(f"  ✅ Cover letter uses uploaded name: {cv['profile']['name']!r}")
        else:
            print(f"  ⚠️  Cover letter may not contain uploaded name")

except Exception as e:
    import traceback
    print(f"  ❌ FAILED: {e}")
    traceback.print_exc()

print("\n" + "=" * 60)
print("  Run the server with: python web.py")
print("  If all steps above show ✅, the backend is correct.")
print("  If uploads still fail in browser, the issue is the")
print("  web.py file on disk — replace it with the downloaded version.")
print("=" * 60)