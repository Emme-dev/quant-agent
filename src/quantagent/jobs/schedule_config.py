"""Just the cron mapping, kept dependency-free (no apscheduler import) so
it's testable in isolation and so adding a new timeframe to
core/timeframes.py without adding it here is something a test can catch,
rather than a silent gap discovered only when someone sets that timeframe
and the scheduler refuses to start."""

# Fires once per bar, a few minutes after the bar closes -- gives the
# exchange time to finalize the candle before we fetch it.
CRON_BY_TIMEFRAME = {
    "1d":  {"hour": 0, "minute": 5},
    "4h":  {"hour": "0,4,8,12,16,20", "minute": 5},
    "1h":  {"minute": 5},
    "15m": {"minute": "2,17,32,47"},
    "5m":  {"minute": "*/5"},
    "1m":  {"minute": "*"},
}
