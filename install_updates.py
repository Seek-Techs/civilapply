# install_updates.py
# 
# HOW TO USE:
# 1. Put this file in your project root folder
# 2. Put ALL the downloaded files (job_parser.py, cv.json, etc.) 
#    in the SAME root folder alongside this script
# 3. Run: python install_updates.py
# 4. It will copy each file to the correct location automatically

import os
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))

# Map: filename you downloaded → where it actually belongs
FILE_MAP = {
    "job_parser.py":          "civil_engineering/job_parser.py",
    "cv.json":                "civil_engineering/data/cv.json",
    "job_filter.py":          "civil_engineering/eligibility/job_filter.py",
    "cv_tailor.py":           "civil_engineering/cv_tailor.py",
    "cover_letter_builder.py":"civil_engineering/cover_letter/cover_letter_builder.py",
    "apply.py":               "apply.py",
    "check_files.py":         "check_files.py",
    "job.py":                  "civil_engineering/domain/job.py",
    "builder.py":              "civil_engineering/intelligence/builder.py",
}

print("=" * 55)
print("  INSTALLING UPDATES")
print("=" * 55)

found   = []
missing = []

for filename, dest_rel in FILE_MAP.items():
    src  = os.path.join(ROOT, filename)
    dest = os.path.join(ROOT, dest_rel)

    if not os.path.exists(src):
        missing.append(filename)
        continue

    # Don't copy if src and dest are the same file
    if os.path.abspath(src) == os.path.abspath(dest):
        print(f"  ✓  {filename} already in place")
        found.append(filename)
        continue

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(src, dest)
    print(f"  ✅  {filename}  →  {dest_rel}")
    found.append(filename)

if missing:
    print(f"\n  ⚠️  These files were not found in {ROOT}:")
    for f in missing:
        print(f"      {f}  — download it and put it in the root folder")

print(f"\n  {len(found)}/{len(FILE_MAP)} files installed")

# Verify the key fixes are now in place
print(f"\n{'─'*55}")
print("  VERIFYING KEY FIXES")
print(f"{'─'*55}")

checks = [
    ("civil_engineering/job_parser.py",  "requirement_patterns",      "years extraction fixed"),
    ("civil_engineering/job_parser.py",  "job_section",               "project type fixed"),
    ("civil_engineering/job_parser.py",  "naira",                     "Nigerian salary detected"),
    ("civil_engineering/data/cv.json",   "Nego Construction",         "real CV loaded"),
    ("civil_engineering/data/cv.json",   "reinforcement inspection",  "detailed bullets loaded"),
    ("civil_engineering/cv_tailor.py",   "_call_cohere",              "Cohere AI connected"),
    ("apply.py",                         "_load_env_file",            "env file loading fixed"),
]

all_good = True
for filepath, signature, description in checks:
    full = os.path.join(ROOT, filepath)
    try:
        content = open(full, encoding='utf-8', errors='replace').read()
        ok = signature in content
        print(f"  {'✓' if ok else '✗'}  {description}")
        if not ok:
            all_good = False
    except FileNotFoundError:
        print(f"  ✗  {description}  (file missing)")
        all_good = False

print()
if all_good:
    print("  ✅ All updates verified. Run: python apply.py")
else:
    print("  ❌ Some files still need updating.")
    print("     Download the missing files and run this script again.")
print("=" * 55)