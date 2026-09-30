"""The most important tests in this repo: they catch lookahead / leakage bugs
that would otherwise only show up as a backtest that looks too good to be true."""
import numpy as np
import pandas as pd
import pytest

from quantagent.features.build import build_features, FEATURE_COLUMNS
from quantagent.features.targets import build_targets, make_training_table


def _make_candles(n=40, seed=0):
    rng = np.random.default_rng(seed)
    ts = [1_700_000_000_000 + i * 86_400_000 for i in range(n)]
    close = 100 * np.cumprod(1 + rng.normal(0, 0.02, n))
    high = close * (1 + rng.uniform(0, 0.01, n))
    low = close * (1 - rng.uniform(0, 0.01, n))
    open_ = close * (1 + rng.normal(0, 0.005, n))
    volume = rng.uniform(1000, 5000, n)
    return pd.DataFrame({"ts": ts, "open": open_, "high": high, "low": low,
                         "close": close, "volume": volume})


def test_features_row_t_unchanged_by_future_rows():
    """Truncating the dataframe after row t must not change row t's features.
    If it does, a feature is peeking at rows beyond t -- a leak."""
    full = _make_candles(40)
    truncated = full.iloc[:25].copy()

    feat_full = build_features(full)
    feat_trunc = build_features(truncated)

    row_t = 20
    for col in FEATURE_COLUMNS:
        a = feat_full.loc[row_t, col]
        b = feat_trunc.loc[row_t, col]
        if pd.isna(a) and pd.isna(b):
            continue
        assert a == pytest.approx(b), f"{col} changed when future rows were removed"


def test_target_uses_future_row_by_design():
    """Sanity check the opposite direction: the target for row t MUST come from
    row t+horizon's close, confirming it's wired correctly (not accidentally
    using row t's own close, which would make it trivially unpredictable/leaked
    the other way)."""
    df = _make_candles(10)
    out = build_targets(df, horizon=1)
    expected = df["close"].iloc[1] / df["close"].iloc[0] - 1
    assert out["target_ret_1d"].iloc[0] == pytest.approx(expected)
    assert pd.isna(out["target_ret_1d"].iloc[-1])  # last row has no future row


def test_no_feature_column_is_the_target():
    """Guards against a future refactor accidentally adding a target/forward
    column into FEATURE_COLUMNS."""
    assert not any(c.startswith("target_") for c in FEATURE_COLUMNS)


def test_training_table_drops_unusable_rows_only():
    df = build_features(_make_candles(30))
    df["symbol"] = "BTC/USD"
    table = make_training_table(df, FEATURE_COLUMNS, horizon=1)
    assert table[FEATURE_COLUMNS].isna().sum().sum() == 0
    assert table["target_ret_1d"].isna().sum() == 0
    assert len(table) < len(df)  # warm-up rows and last row were correctly dropped


def test_training_table_keeps_symbols_independent():
    """Two symbols' features/targets must never mix across the groupby/concat."""
    a = build_features(_make_candles(30, seed=1))
    a["symbol"] = "A/USD"
    b = build_features(_make_candles(30, seed=2))
    b["symbol"] = "B/USD"
    combined = pd.concat([a, b], ignore_index=True)
    table = make_training_table(combined, FEATURE_COLUMNS, horizon=1)
    assert set(table["symbol"].unique()) == {"A/USD", "B/USD"}
    # each symbol's row count in the output should match a standalone run
    for sym, src in [("A/USD", a), ("B/USD", b)]:
        solo = make_training_table(src, FEATURE_COLUMNS, horizon=1)
        assert (table["symbol"] == sym).sum() == len(solo)
