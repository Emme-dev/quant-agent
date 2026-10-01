"""Prediction targets. build_targets uses close.shift(-horizon), i.e. it reaches
INTO THE FUTURE relative to row t on purpose -- that's the label, not a feature.
It must never be joined back in as an input feature. build_features (features/build.py)
and build_targets are kept in separate functions specifically so a future column
can't accidentally end up in FEATURE_COLUMNS.

horizon is in BARS, not calendar days -- horizon=1 means "the next bar,"
whichever timeframe that bar represents. This matches how the daily-rank
strategy rebalances (once per bar), so the target always lines up with what
the strategy is actually trying to predict. Column names use a 'b' suffix
(target_ret_1b, not target_ret_1d) so they aren't misread as calendar days
on a non-daily timeframe."""
import pandas as pd


def build_targets(df: pd.DataFrame, horizon: int = 1) -> pd.DataFrame:
    out = df.copy()
    fwd_ret = out["close"].shift(-horizon) / out["close"] - 1
    out[f"target_ret_{horizon}b"] = fwd_ret
    # 3-class label: down / flat / up, flat = within +/-0.5%
    band = 0.005
    out[f"target_class_{horizon}b"] = pd.cut(
        fwd_ret, bins=[-float("inf"), -band, band, float("inf")],
        labels=["down", "flat", "up"],
    )
    return out


def make_training_table(feat_df: pd.DataFrame, feature_columns: list[str],
                        horizon: int = 1) -> pd.DataFrame:
    """One call site that does load -> features -> targets -> drop unusable rows,
    per symbol, so no row's features and target are computed from a different
    symbol's series after a naive concat."""
    parts = []
    for sym, g in feat_df.groupby("symbol", sort=False):
        g = g.sort_values("ts")
        g = build_targets(g, horizon=horizon)
        parts.append(g)
    full = pd.concat(parts, ignore_index=True)

    target_col = f"target_ret_{horizon}b"
    needed = feature_columns + [target_col, f"target_class_{horizon}b",
                                "symbol", "ts", "date"]
    full = full.dropna(subset=feature_columns + [target_col])
    return full[needed]
