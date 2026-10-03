"""Day 7: runs the daily job unattended, on a cadence matching
config/settings.yaml's timeframe. This is the last thing built on purpose --
it's what turns 'a script I run by hand' into 'a system that trades without
me watching it', so everything underneath it (risk rules, kill switch,
paper broker, data-quality checks) should already be trusted before this
runs on its own.

python scripts/run_scheduler.py starts it; it then blocks and fires on
schedule until stopped with Ctrl+C. For real unattended operation (surviving
a reboot, running when you're not logged in), run that script under a
process manager -- systemd on Linux, Task Scheduler on Windows, pm2, etc.
This module itself doesn't daemonize or auto-restart on crash."""
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from ..core.config import settings
from ..core.logging import get_logger
from .daily_run import run_and_report
from .schedule_config import CRON_BY_TIMEFRAME

log = get_logger("scheduler")


def _run_job():
    log.info("Scheduled run starting at %s", datetime.now(timezone.utc).isoformat())
    try:
        run_and_report()
    except Exception:
        # A scheduled job must never take the whole process down -- log the
        # full traceback and let the NEXT scheduled run try again.
        log.exception("Scheduled run FAILED. Will retry on the next cycle.")


def start():
    cfg = settings()
    timeframe = cfg["timeframe"]
    cron_kwargs = CRON_BY_TIMEFRAME.get(timeframe)
    if cron_kwargs is None:
        raise ValueError(
            f"No cron schedule defined for timeframe '{timeframe}'. "
            f"Known: {list(CRON_BY_TIMEFRAME)}"
        )

    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(_run_job, CronTrigger(**cron_kwargs), id="daily_job",
                 misfire_grace_time=300)
    log.info("Scheduler started for timeframe=%s (cron=%s). Ctrl+C to stop.",
             timeframe, cron_kwargs)
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")


if __name__ == "__main__":
    start()
