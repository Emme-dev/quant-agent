"""Day 6 entry point: python scripts/run_daily_agent.py
Runs the full daily pipeline, prints a plain-English report, and saves it to
data/reports/<timestamp>.md. This is the manual/on-demand way to trigger the
same job scripts/run_scheduler.py (Day 7) runs automatically on a cadence --
both go through quantagent.jobs.daily_run.run_and_report()."""
from quantagent.jobs.daily_run import run_and_report


def main():
    result, report, path = run_and_report()
    print("\n" + report + "\n")


if __name__ == "__main__":
    main()
