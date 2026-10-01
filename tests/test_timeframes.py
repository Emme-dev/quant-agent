"""core/timeframes.py conversion tests. This module is the single source of
truth every other module leans on to stay correct across bar sizes -- an
off-by-one here would silently corrupt feature windows, walk-forward splits,
and Sharpe/CAGR annualization all at once."""
import pytest

from quantagent.core.timeframes import bars_per_day, periods_per_year, days_to_bars


def test_bars_per_day_daily_is_one():
    assert bars_per_day("1d") == 1


def test_bars_per_day_intraday():
    assert bars_per_day("1h") == 24
    assert bars_per_day("4h") == 6
    assert bars_per_day("15m") == 96
    assert bars_per_day("5m") == 288
    assert bars_per_day("1m") == 1440


def test_periods_per_year_daily_matches_calendar_year():
    assert periods_per_year("1d") == 365


def test_periods_per_year_scales_with_bar_size():
    assert periods_per_year("4h") == pytest.approx(365 * 6)
    assert periods_per_year("1h") == pytest.approx(365 * 24)


def test_days_to_bars_identity_on_daily():
    """This is the backward-compatibility guarantee: for '1d' data, every
    calendar-day window converts to the exact same bar count as before this
    change -- so existing daily behavior is untouched."""
    for n in [1, 3, 7, 14, 180, 30]:
        assert days_to_bars(n, "1d") == n


def test_days_to_bars_scales_on_intraday():
    assert days_to_bars(7, "1h") == 7 * 24
    assert days_to_bars(1, "15m") == 96


def test_days_to_bars_never_zero():
    # a fractional or tiny day count must still round to at least 1 bar
    assert days_to_bars(0, "1d") == 1
    assert days_to_bars(0.01, "1h") == 1


def test_unknown_timeframe_raises():
    with pytest.raises(ValueError):
        bars_per_day("3d")
