"""
setup.py — Run once to set up CivilApply.

Usage:
    python setup.py
"""

import os, sys, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))

def run(cmd, desc):
    print(f"  → {desc}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"    ⚠  Warning: {result.stderr.strip()[:200]}")
    else:
        print(f"    ✓  Done")
    return result.returncode == 0

print("\n══════════════════════════════════════════")
print("  CivilApply — Setup")
print("══════════════════════════════════════════\n")

# 1. Python version
v = sys.version_info
print(f"Python {v.major}.{v.minor}.{v.micro}", "✓" if v >= (3, 9) else "⚠ (3.9+ recommended)")

# 2. Core packages only — no Playwright, no browser needed
print("\n[1/3] Installing packages...")
run(f"{sys.executable} -m pip install flask requests beautifulsoup4 reportlab pdfplumber gunicorn --quiet", "packages")

# 3. Check static/app.js
print("\n[2/3] Checking static/ folder...")
static_dir = os.path.join(HERE, 'static')
app_js     = os.path.join(static_dir, 'app.js')
os.makedirs(static_dir, exist_ok=True)

if not os.path.exists(app_js):
    print(f"  ⚠  static/app.js not found — download it from GitHub")
else:
    size = os.path.getsize(app_js)
    print(f"  ✓  static/app.js found ({size:,} bytes)")

# 4. Verify imports
print("\n[3/3] Verifying imports...")
errors = []
for module in ['flask', 'requests', 'bs4', 'reportlab', 'pdfplumber']:
    try:
        __import__(module)
        print(f"  ✓  {module}")
    except ImportError as e:
        print(f"  ✗  {module}: {e}")
        errors.append(module)

# Check .env / SMTP hint
print("\n[Optional] Email sending (for Apply by Email feature):")
smtp = os.environ.get('SMTP_EMAIL', '')
if smtp:
    print(f"  ✓  SMTP_EMAIL set ({smtp})")
else:
    print("  ℹ  SMTP_EMAIL not set — create a .env file with SMTP_EMAIL and SMTP_PASSWORD")
    print("     to enable the 'Apply by Email' feature. Not required to run the app.")

# Summary
print("\n══════════════════════════════════════════")
if errors:
    print(f"  ⚠  Missing: {', '.join(errors)}")
    print(f"     Run: pip install {' '.join(errors)}")
else:
    print("  ✓  All dependencies installed!")
print(f"\n  Start the server:  python web.py")
print(f"  Open in browser:   http://127.0.0.1:5000")
print("══════════════════════════════════════════\n")
