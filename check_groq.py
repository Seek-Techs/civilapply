# check_groq.py
# Run this to diagnose Groq connection issues: python check_groq.py

import os
import sys
import json
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.abspath(__file__))

# ── Step 1: Load .env file ────────────────────────────────────────────────────
print("=" * 55)
print("  GROQ CONNECTION DIAGNOSTIC")
print("=" * 55)

env_path = os.path.join(ROOT, ".env")
print(f"\n[1] Looking for .env file at:")
print(f"    {env_path}")

if os.path.exists(env_path):
    print("    ✓ File exists")
    with open(env_path, "r", encoding="utf-8") as f:
        raw_contents = f.read()

    print(f"\n[2] Raw .env file contents (exactly as stored):")
    print("    ---")
    for i, line in enumerate(raw_contents.splitlines(), 1):
        # Show the line but mask most of any key value
        if "=" in line and "API_KEY" in line.upper():
            key, val = line.split("=", 1)
            val = val.strip().strip('"').strip("'")
            masked = val[:8] + "..." + val[-4:] if len(val) > 12 else val
            print(f"    Line {i}: {key}={masked}  (length: {len(val)} chars)")
        else:
            print(f"    Line {i}: {repr(line)}")
    print("    ---")
else:
    print("    ✗ File NOT FOUND")
    print("\n    Create a file named exactly '.env' in:")
    print(f"    {ROOT}")
    print("    Containing this single line:")
    print("    GROQ_API_KEY=gsk_your_key_here")
    sys.exit(1)

# ── Step 2: Parse the key ─────────────────────────────────────────────────────
api_key = None
for line in raw_contents.splitlines():
    line = line.strip()
    if line.startswith("GROQ_API_KEY"):
        _, val = line.split("=", 1)
        api_key = val.strip().strip('"').strip("'")
        break

print(f"\n[3] GROQ_API_KEY extracted:")
if api_key:
    print(f"    First 8 chars : {api_key[:8]}")
    print(f"    Last 4 chars  : {api_key[-4:]}")
    print(f"    Total length  : {len(api_key)} characters")
    print(f"    Starts with gsk_ : {'Yes ✓' if api_key.startswith('gsk_') else 'NO ✗ — Groq keys must start with gsk_'}")
else:
    print("    ✗ Could not find GROQ_API_KEY in .env file")
    print("    Make sure the line is exactly:  GROQ_API_KEY=gsk_...")
    sys.exit(1)

# ── Step 3: Test the key against Groq ────────────────────────────────────────
print(f"\n[4] Testing key against Groq API...")

# First try listing models — lightweight call, no tokens used
req = urllib.request.Request(
    "https://api.groq.com/openai/v1/models",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    method="GET",
)

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        data   = json.loads(resp.read().decode("utf-8"))
        models = sorted(m["id"] for m in data.get("data", []))
        print(f"    ✓ Authentication successful!")
        print(f"\n[5] Available models on your account ({len(models)} total):")
        for m in models:
            print(f"    - {m}")

except urllib.error.HTTPError as e:
    body = ""
    try:
        body = e.read().decode("utf-8")
        err  = json.loads(body).get("error", {})
        msg  = err.get("message", body)
    except Exception:
        msg = body or str(e)

    print(f"    ✗ HTTP {e.code} error from Groq:")
    print(f"    {msg}")

    if e.code == 401:
        print("\n    DIAGNOSIS: Invalid API key.")
        print("    → Go to console.groq.com → API Keys → create a new key")
        print("    → Copy the full key (starts with gsk_) into your .env file")
    elif e.code == 403:
        print("\n    DIAGNOSIS: Key is valid but access is denied.")
        print("    → This can happen if your account needs email verification")
        print("    → Check your email for a verification link from Groq")
        print("    → Or try logging out and back in at console.groq.com")
    else:
        print(f"\n    Unexpected error code: {e.code}")

except urllib.error.URLError as e:
    print(f"    ✗ Cannot reach Groq servers: {e.reason}")
    print("    → Check your internet connection")

except Exception as e:
    print(f"    ✗ Unexpected error: {type(e).__name__}: {e}")

print("\n" + "=" * 55)