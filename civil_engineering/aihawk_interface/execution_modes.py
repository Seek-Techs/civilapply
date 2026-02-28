# civil_engineering/aihawk_interface/execution_modes.py

EXECUTION_MODES = {
    "dry_run": {
        "apply": False,
        "log_only": True
    },
    "live_run": {
        "apply": True,
        "log_only": False
    }
}
