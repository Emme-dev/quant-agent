"""Pure test: no apscheduler import needed, since CRON_BY_TIMEFRAME lives in
its own dependency-free module. Mainly guards against the exact kind of
drift this project has hit before (Day 5's stale target_class_1d, the
duplicated pipeline logic fixed in Day 6): someone adds a timeframe to
core/timeframes.py and forgets the scheduler has no idea how to run it."""
from quantagent.core.timeframes import BAR_SECONDS
from quantagent.jobs.schedule_config import CRON_BY_TIMEFRAME


def test_every_known_timeframe_has_a_cron_entry():
    missing = set(BAR_SECONDS) - set(CRON_BY_TIMEFRAME)
    assert not missing, f"timeframe(s) with no cron schedule: {missing}"


def test_no_cron_entry_for_an_unknown_timeframe():
    extra = set(CRON_BY_TIMEFRAME) - set(BAR_SECONDS)
    assert not extra, f"cron schedule defined for unknown timeframe(s): {extra}"


def test_cron_entries_are_nonempty_dicts():
    for tf, kwargs in CRON_BY_TIMEFRAME.items():
        assert isinstance(kwargs, dict) and kwargs, f"{tf} has an empty/invalid cron spec"
