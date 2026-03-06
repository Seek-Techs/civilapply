"""
setup.py — Run once to set up CivilApply correctly.

Usage:
    python setup.py

What it does:
    1. Checks Python version
    2. Installs required packages
    3. Installs Playwright + Chromium browser
    4. Creates the static/ folder if missing
    5. Verifies everything works
"""

import os, sys, subprocess, shutil

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

# 2. Core packages
print("\n[1/4] Installing Python packages...")
run(f"{sys.executable} -m pip install flask requests beautifulsoup4 playwright --quiet", "packages")

# 3. Playwright browser
print("\n[2/4] Installing Playwright Chromium browser...")
run(f"{sys.executable} -m playwright install chromium", "Playwright Chromium")

# 4. static/ folder
print("\n[3/4] Checking static/ folder...")
static_dir = os.path.join(HERE, 'static')
app_js     = os.path.join(static_dir, 'app.js')

os.makedirs(static_dir, exist_ok=True)

if not os.path.exists(app_js):
    print(f"  ⚠  static/app.js not found!")
    print(f"     Place app.js in: {static_dir}")
else:
    size = os.path.getsize(app_js)
    print(f"  ✓  static/app.js found ({size} bytes)")

# 5. Verify imports
print("\n[4/4] Verifying imports...")
errors = []
for module in ['flask', 'requests', 'bs4']:
    try:
        __import__(module)
        print(f"  ✓  {module}")
    except ImportError as e:
        print(f"  ✗  {module}: {e}")
        errors.append(module)

try:
    from playwright.sync_api import sync_playwright
    print("  ✓  playwright")
except ImportError:
    print("  ✗  playwright — run: pip install playwright && python -m playwright install chromium")
    errors.append('playwright')

# Summary
print("\n══════════════════════════════════════════")
if errors:
    print(f"  ⚠  Issues: {', '.join(errors)}")
    print("  Job scraping may not work until playwright is installed.")
else:
    print("  ✓  All dependencies installed!")

print(f"\n  Start the server:  python web.py")
print(f"  Open in browser:   http://127.0.0.1:5000")
print("══════════════════════════════════════════\n")
