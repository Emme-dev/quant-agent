"""Feature engineering. Every feature here uses only data up to and
including row t — never a future row. That rule is what test_no_lookahead
in tests/test_features.py checks."""
import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    "ret_1d", "ret_3d", "ret_7d", "ret_14d",
    "vol_7d", "vol_14d",
    "mom_7d", "mom_14d",
    "vol_chg_7d",
    "hl_range",
    "dist_from_ma7", "dist_from_ma14",
]


def _load_candles(engine, exchange: str, symbol: str, timeframe: str) -> pd.DataFrame:
    q = """
        SELECT ts, open, high, low, close, volume
        FROM candles
        WHERE exchange = :exchange AND symbol = :symbol AND timeframe = :timeframe
        ORDER BY ts ASC
    """
    df = pd.read_sql(q, engine, params={"exchange": exchange, "symbol": symbol,
                                        "timeframe": timeframe})
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """df must have columns: ts, open, high, low, close, volume, sorted by ts asc.
    Returns df with FEATURE_COLUMNS (+ a derived 'date') appended. Self-contained:
    does not depend on the caller having added 'date' first. Rows without enough
    history are NaN and should be dropped by the caller (they're not usable,
    not a leak)."""
    out = df.copy()
    if "date" not in out.columns:
        out["date"] = pd.to_datetime(out["ts"], unit="ms", utc=True)
    c = out["close"]

    out["ret_1d"] = c.pct_change(1)
    out["ret_3d"] = c.pct_change(3)
    out["ret_7d"] = c.pct_change(7)
    out["ret_14d"] = c.pct_change(14)

    daily_ret = c.pct_change(1)
    out["vol_7d"] = daily_ret.rolling(7).std()
    out["vol_14d"] = daily_ret.rolling(14).std()

    out["mom_7d"] = c / c.shift(7) - 1
    out["mom_14d"] = c / c.shift(14) - 1

    vol_ma7 = out["volume"].rolling(7).mean()
    out["vol_chg_7d"] = out["volume"] / vol_ma7 - 1

    out["hl_range"] = (out["high"] - out["low"]) / c

    ma7 = c.rolling(7).mean()
    ma14 = c.rolling(14).mean()
    out["dist_from_ma7"] = c / ma7 - 1
    out["dist_from_ma14"] = c / ma14 - 1

    return out


def build_features_for_universe(engine, exchange: str, symbols: list[str],
                                 timeframe: str) -> pd.DataFrame:
    frames = []
    for sym in symbols:
        raw = _load_candles(engine, exchange, sym, timeframe)
        if raw.empty:
            continue
        feat = build_features(raw)
        feat["symbol"] = sym
        frames.append(feat)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
