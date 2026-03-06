# run.py
#
# ── HOW TO USE THIS FILE ─────────────────────────────────────────────────────
# This is your launcher. Place it in the ROOT of your project:
#
#   C:\Users\Admin\Jobs_Applier_AI_Agent_AIHawk\run.py   ← here
#
# Then run it with ONE of these commands from that same root folder:
#
#   python run.py
#
# Or just double-click run.py in Windows Explorer if Python is associated.
#
# ── WHY THIS FILE EXISTS ─────────────────────────────────────────────────────
# Python needs to know WHERE your packages are before it can import them.
# "Packages" are folders with an __init__.py file — like civil_engineering/.
#
# When you run a file, Python adds THAT FILE'S FOLDER to its search path.
# So if you run civil_engineering/pipeline/run_application.py directly,
# Python looks for packages inside the pipeline/ folder — and finds nothing.
#
# This launcher lives at the ROOT, so Python's search path includes the root,
# where civil_engineering/ lives. All imports then work correctly.

import sys
import os

# Make absolutely sure the root folder is on Python's path
# __file__ = this file's path = C:\...\Jobs_Applier_AI_Agent_AIHawk\run.py
# os.path.dirname(__file__) = C:\...\Jobs_Applier_AI_Agent_AIHawk\
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Now import and run the pipeline
from civil_engineering.pipeline.run_application import main

if __name__ == "__main__":
    main()