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
    folds = walk_forward_splits(dates, n_splits=4, min_train_days=100, test_days=20)
    assert len(folds) > 0
    for f in folds:
        train_dates = dates.iloc[f.train_idx]
        test_dates = dates.iloc[f.test_idx]
        assert train_dates.max() < test_dates.min(), "train row dated on/after a test row"
        assert train_dates.max() == f.train_end_date


def test_folds_roll_forward():
    dates = _dates(300)
    folds = walk_forward_splits(dates, n_splits=4, min_train_days=100, test_days=20)
    for a, b in zip(folds, folds[1:]):
        assert b.train_end_date > a.train_end_date, "folds did not advance in time"


def test_multi_symbol_dates_stay_grouped():
    """Same date, two symbols -- both rows must land on the same side."""
    base = _dates(300)
    dates = pd.concat([base, base], ignore_index=True)  # duplicate every date
    folds = walk_forward_splits(dates, n_splits=3, min_train_days=100, test_days=20)
    for f in folds:
        train_dates = set(dates.iloc[f.train_idx])
        test_dates = set(dates.iloc[f.test_idx])
        assert train_dates.isdisjoint(test_dates), "a date appears on both sides of a fold"


def test_raises_when_not_enough_history():
    dates = _dates(50)
    try:
        walk_forward_splits(dates, n_splits=3, min_train_days=100, test_days=20)
        assert False, "expected ValueError for insufficient history"
    except ValueError:
        pass
