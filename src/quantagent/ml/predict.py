"""Turns the latest feature row per symbol into a Signal. This is what the
daily agent pipeline calls -- it never retrains, only scores."""
import pandas as pd
from ..core.db import session_scope
from ..core.models import Signal
from .registry import load_model


def latest_row_per_symbol(feat_df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    """The most recent COMPLETE feature row per symbol (all feature columns
    non-null). Using an incomplete row would mean predicting from partial
    data, not a leak but a silent quality bug -- so we exclude it."""
    usable = feat_df.dropna(subset=feature_columns)
    idx = usable.groupby("symbol")["ts"].idxmax()
    return usable.loc[idx].reset_index(drop=True)


def predict_latest(feat_df: pd.DataFrame, account_id: int, run_id: int | None = None,
                   version: str | None = None) -> pd.DataFrame:
    model, meta = load_model(version)
    latest = latest_row_per_symbol(feat_df, meta["feature_columns"])
    if latest.empty:
        return latest
    latest["score"] = model.predict(latest[meta["feature_columns"]])

    with session_scope() as s:
        s.add_all(
            Signal(account_id=account_id, run_id=run_id, symbol=row.symbol,
                   ts=int(row.ts), score=float(row.score), model_version=meta["version"])
            for row in latest.itertuples()
        )
    return latest[["symbol", "ts", "date", "score", "close"]].sort_values("score", ascending=False)
