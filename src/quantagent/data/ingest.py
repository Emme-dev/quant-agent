import time
from sqlalchemy import func, select
from ..core.db import session_scope
from ..core.logging import get_logger
from ..core.models import Candle
from . import exchange as exmod

log = get_logger("ingest")


def sync_symbol(ex, exchange_name: str, symbol: str, timeframe: str,
                history_days: int) -> int:
    """Idempotent: only fetches candles newer than what is stored."""
    with session_scope() as s:
        last = s.scalar(
            select(func.max(Candle.ts)).where(
                Candle.exchange == exchange_name,
                Candle.symbol == symbol,
                Candle.timeframe == timeframe,
            )
        )
        if last is None:
            since = int(time.time() * 1000) - history_days * 86_400_000
        else:
            since = last + exmod.TF_MS[timeframe]
        rows = exmod.fetch_ohlcv_all(ex, symbol, timeframe, since)
        rows = [r for r in rows if last is None or r[0] > last]
        s.add_all(
            Candle(exchange=exchange_name, symbol=symbol, timeframe=timeframe,
                   ts=int(r[0]), open=r[1], high=r[2], low=r[3],
                   close=r[4], volume=r[5])
            for r in rows
        )
    log.info("%s: +%d candles", symbol, len(rows))
    return len(rows)


def sync_universe(ex, exchange_name, symbols, timeframe, history_days):
    total = 0
    for sym in symbols:
        try:
            total += sync_symbol(ex, exchange_name, sym, timeframe, history_days)
        except Exception as e:  # one bad pair must not stop the batch
            log.warning("%s failed: %s", sym, e)
    return total
