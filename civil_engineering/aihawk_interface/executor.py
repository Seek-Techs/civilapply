# civil_engineering/aihawk_interface/executor.py

from civil_engineering.aihawk_interface.execution_modes import EXECUTION_MODES


def execute_plan(plan, mode="dry_run"):
    settings = EXECUTION_MODES[mode]

    if not settings["apply"]:
        print(f"[DRY RUN] Would apply to {plan['job_title']} via {plan['platform']}")
        return

    # ---- LIVE EXECUTION (placeholder) ----
    print(f"[LIVE] Applying to {plan['job_title']} via {plan['platform']}")
    # Here is where AIHawk hooks in
