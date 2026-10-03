"""Defines WHAT the daily job does, separate from WHEN it runs
(jobs/scheduler.py) or how a human triggers it manually
(scripts/run_daily_agent.py). Both of those call run_and_report() rather
than each having their own copy of 'run the pipeline, then save the
report' -- the same duplication fix applied to the pipeline itself in
agent/orchestrator.py."""
from datetime import datetime, timezone
from pathlib import Path

from ..agent.orchestrator import run_daily_pipeline
from ..agent.report import generate_report
from ..core.logging import get_logger

log = get_logger("daily_run")


def run_and_report(account_name: str | None = None):
    """Returns (PipelineResult, report_text, report_path)."""
    result = run_daily_pipeline(account_name=account_name)
    report = generate_report(result)

    out_dir = Path("data/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = out_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S')}.md"
    fname.write_text(report)
    log.info("Report saved to %s", fname)

    return result, report, fname
