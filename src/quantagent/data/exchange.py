import time
import ccxt

TF_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "1h": 3_600_000,
         "4h": 14_400_000, "1d": 86_400_000}


def make_exchange(name: str, keys: dict | None = None):
    cls = getattr(ccxt, name)
    return cls({"enableRateLimit": True, **(keys or {})})


def fetch_ohlcv_all(ex, symbol: str, timeframe: str, since_ms: int,
                    limit: int = 1000) -> list[list]:
    """Paginate forward from since_ms to now. Drops the still-forming candle."""
    out, cursor = [], since_ms
    step = TF_MS[timeframe]
    while True:
        batch = ex.fetch_ohlcv(symbol, timeframe, since=cursor, limit=limit)
        if not batch:
            break
        out.extend(batch)
        nxt = batch[-1][0] + step
        if nxt <= cursor or len(batch) < 2:
            break
        cursor = nxt
    now = int(time.time() * 1000)
    return [c for c in out if c[0] + step <= now]
