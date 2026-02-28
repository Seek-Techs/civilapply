# civil_engineering/aihawk_interface/run_executor.py

import json
from pathlib import Path

from civil_engineering.apply_strategy.strategy_engine import decide_apply_strategy
from civil_engineering.aihawk_interface.execution_plan import build_execution_plan
from civil_engineering.aihawk_interface.executor import execute_plan
from civil_engineering.apply_strategy.safety_config import MAX_APPLICATIONS_PER_RUN
from civil_engineering.aihawk_interface.audit_logger import log_execution
from civil_engineering.aihawk_interface.execution_limits import can_apply, register_application
from civil_engineering.aihawk_interface.safety_rules import is_safe_to_apply
from civil_engineering.aihawk_interface.throttle import throttle
from civil_engineering.domain import job
from civil_engineering.monitoring.metrics_store import update_metrics, load_metrics
from civil_engineering.monitoring.anomaly_detector import detect_anomaly
from civil_engineering.feedback.outcome_store import record_outcome
from civil_engineering.feedback.decision_log_store import store_decision
from civil_engineering.explainability.explanation_engine import generate_explanation
from civil_engineering.explainability.explanation_builder import build_explanation
from civil_engineering.explainability.explanation_store import store_explanation
from civil_engineering.normalization.signal_normalizer import normalize_signals




OUTPUT_DIR = Path("civil_engineering/output")
ALLOWED_MODES = {"dry_run", "live"}


def run(mode="dry_run"):
    update_metrics(lambda m: m.update({
        "total_runs": m["total_runs"] + 1
    }))

    if mode not in ALLOWED_MODES:
        raise ValueError(f"Invalid execution mode: {mode}")

    if mode == "live":
        raise RuntimeError(
            "LIVE MODE DISABLED — remove this guard intentionally to enable."
        )

    global_ranking_file = OUTPUT_DIR / "global_job_ranking.json"
    if not global_ranking_file.exists():
        raise FileNotFoundError("Run global ranking first.")

    with open(global_ranking_file, "r", encoding="utf-8") as f:
        approved_jobs = json.load(f)

    metrics = load_metrics()
    anomaly = detect_anomaly(metrics)
    if anomaly:
        print(f"🛑 AUTO-SHUTDOWN: {anomaly['message']}")
        return

    applied_count = 0

    for job in approved_jobs:
        if applied_count >= MAX_APPLICATIONS_PER_RUN:
            print("[SAFETY] Application limit reached. Stopping.")
            break

        decision = decide_apply_strategy(job)
        # from civil_engineering.explainability.explanation_builder import build_explanation
        # from civil_engineering.explainability.explanation_store import record_explanation

        # Human override hook (manual layer)

        decision_log = job.get("decision_log", [])

        blocks = []
        if not is_safe_to_apply(job):
            blocks.append("confidence_below_threshold")

        explanation = build_explanation(
            job=job,
            decision=decision,
            decision_log=decision_log,
            blocks=blocks
        )

        store_explanation(explanation)



        # Store decision context for learning
        normalized_signals = job["normalized_signals"]
        store_decision(
            job_id=job["job_id"],
            signals=normalized_signals
        )

        # Only auto-apply decisions continue
        if decision.get("decision") != "auto_apply":
            continue

        # 🔒 Confidence safety gate
        if not is_safe_to_apply(job):
            print(f"⏭ Skipping {job['job_title']} — confidence too low.")
            update_metrics(lambda m: m.update({
                "applications_blocked": m["applications_blocked"] + 1
            }))
            continue

        # 🔒 Daily cap
        if not can_apply():
            print("🛑 Daily application limit reached.")
            break

        update_metrics(lambda m: m.update({
            "auto_apply_count": m["auto_apply_count"] + 1
        }))

        log_execution({
            "job_id": job["job_id"],
            "job_title": job["job_title"],
            "confidence": job["confidence"],
            "rank": job["rank"],
            "decision": decision.get("decision"),
            "platform": decision.get("platform"),
            "reason": decision.get("reason"),
            "explanation": explanation,
            "mode": mode
        })


        print(f"[DRY RUN] Would apply to {job['job_title']} via {decision.get('platform')}")

        throttle()
        register_application()

        record_outcome(
            job_id=job["job_id"],
            outcome="applied",
            notes=explanation["summary"]
        )


        applied_count += 1

        update_metrics(lambda m: m.update({
            "applications_attempted": m["applications_attempted"] + 1,
            "auto_apply_count": m["auto_apply_count"] + 1
        }))

        explanation = build_explanation(
            job=job,
            decision=decision,
            decision_log=job.get("decision_log", [])
        )

        store_explanation(explanation)


if __name__ == "__main__":
    run(mode="dry_run")
