"""Walk-forward split tests. These run without lightgbm installed -- they
only check the date arithmetic, which is the part that actually determines
whether the model leaks the future."""
import numpy as np
import pandas as pd

from quantagent.ml.train import walk_forward_splits


def _dates(n=300):
    return pd.Series(pd.date_range("2024-01-01", periods=n, freq="D"))


def test_train_never_overlaps_test_in_time():
    dates = _dates(300)
    folds = walk_forward_splits(dates, n_splits=4, min_train_periods=100, test_periods=20)
    assert len(folds) > 0
    for f in folds:
        train_dates = dates.iloc[f.train_idx]
        test_dates = dates.iloc[f.test_idx]
        assert train_dates.max() < test_dates.min(), "train row dated on/after a test row"
        assert train_dates.max() == f.train_end_date


def test_folds_roll_forward():
    dates = _dates(300)
    folds = walk_forward_splits(dates, n_splits=4, min_train_periods=100, test_periods=20)
    for a, b in zip(folds, folds[1:]):
        assert b.train_end_date > a.train_end_date, "folds did not advance in time"


def test_multi_symbol_dates_stay_grouped():
    """Same date, two symbols -- both rows must land on the same side."""
    base = _dates(300)
    dates = pd.concat([base, base], ignore_index=True)  # duplicate every date
    folds = walk_forward_splits(dates, n_splits=3, min_train_periods=100, test_periods=20)
    for f in folds:
        train_dates = set(dates.iloc[f.train_idx])
        test_dates = set(dates.iloc[f.test_idx])
        assert train_dates.isdisjoint(test_dates), "a date appears on both sides of a fold"


def test_scales_down_instead_of_raising_when_history_is_thin():
    """50 bars is less than the requested 100+20=120, but well above the
    hard floor -- this must produce a real (smaller) fold, not raise."""
    dates = _dates(50)
    folds = walk_forward_splits(dates, n_splits=3, min_train_periods=100, test_periods=20)
    assert len(folds) >= 1
    f = folds[0]
    train_dates = dates.iloc[f.train_idx]
    test_dates = dates.iloc[f.test_idx]
    assert train_dates.max() < test_dates.min(), "scaled-down fold still must not leak"
    assert len(f.train_idx) + len(f.test_idx) <= 50


def test_scaling_reproduces_reported_thin_1h_scenario():
    """Regression test for the exact case that used to crash: 360 bars
    available, caller wants 720 train + 120 test (the equivalent of
    min_train_days=30, test_days=5 on a 1h timeframe). Must not raise."""
    dates = _dates(360)
    folds = walk_forward_splits(dates, n_splits=5, min_train_periods=720, test_periods=120)
    assert len(folds) >= 1
    for f in folds:
        train_dates = dates.iloc[f.train_idx]
        test_dates = dates.iloc[f.test_idx]
        assert train_dates.max() < test_dates.min()


def test_raises_only_when_truly_insufficient():
    """Below the hard floor (MIN_BARS_FOR_ANY_SPLIT), no amount of scaling
    helps -- this must still raise clearly rather than produce a
    meaningless 2-bar fold."""
    dates = _dates(8)
    try:
        walk_forward_splits(dates, n_splits=3, min_train_periods=100, test_periods=20)
        assert False, "expected ValueError for genuinely insufficient history"
    except ValueError:
        pass


def test_scaled_down_folds_still_never_leak_across_many_ratios():
    """Sweep several thin-data scenarios and confirm the no-leak property
    (train strictly before test) holds under scaling, not just the exact
    reported case."""
    for n_bars, want_train, want_test in [(50, 100, 20), (120, 500, 50),
                                          (15, 100, 20), (360, 720, 120)]:
        dates = _dates(n_bars)
        folds = walk_forward_splits(dates, n_splits=5, min_train_periods=want_train,
                                    test_periods=want_test)
        for f in folds:
            train_dates = dates.iloc[f.train_idx]
            test_dates = dates.iloc[f.test_idx]
            assert train_dates.max() < test_dates.min(), \
                f"leak at n_bars={n_bars}, want_train={want_train}, want_test={want_test}"
