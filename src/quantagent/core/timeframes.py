"""Single source of truth for converting between a configured timeframe
(1m, 5m, 15m, 1h, 4h, 1d, ...) and calendar time. Every other module that
needs to know 'how many bars is 7 days' or 'how many bars in a year' should
import from here rather than hardcoding an assumption that bars == days."""

BAR_SECONDS = {
    "1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14_400, "1d": 86_400,
}


def bars_per_day(timeframe: str) -> float:
    if timeframe not in BAR_SECONDS:
        raise ValueError(f"Unknown timeframe '{timeframe}'. Known: {list(BAR_SECONDS)}")
    return 86_400 / BAR_SECONDS[timeframe]


def periods_per_year(timeframe: str) -> float:
    """For annualizing Sharpe/CAGR: how many bars occur in a 365-day year."""
    return 365 * bars_per_day(timeframe)


def days_to_bars(days: float, timeframe: str) -> int:
    """Converts a calendar-day window (e.g. '7-day return') into the number
    of bars that spans on the given timeframe. Always at least 1 bar."""
    return max(1, round(days * bars_per_day(timeframe)))
