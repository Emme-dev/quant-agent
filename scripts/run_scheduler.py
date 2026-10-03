"""Day 7 entry point: python scripts/run_scheduler.py
Starts unattended scheduled trading -- runs the same job as
scripts/run_daily_agent.py automatically, on a cadence matching
config/settings.yaml's timeframe. Runs in the foreground (Ctrl+C to stop).
For real unattended operation, run this under a process manager so it
survives a reboot or crash -- see jobs/scheduler.py's docstring."""
from quantagent.jobs.scheduler import start

if __name__ == "__main__":
    start()
