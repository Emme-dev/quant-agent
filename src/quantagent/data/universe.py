from sqlalchemy import select, distinct

from ..core.config import settings
from ..core.models import Candle


def build_universe(ex) -> list[str]:
    """Top-N liquid spot pairs against the quote currency."""
    cfg = settings()
    quote, uni = cfg["quote"], cfg["universe"]
    ex.load_markets()
    tickers = ex.fetch_tickers()
    rows = []
    for sym, t in tickers.items():
        m = ex.markets.get(sym)
        if not m or not m.get("spot") or not m.get("active", True):
            continue
        if m["quote"] != quote or m["base"] in uni["exclude_bases"]:
            continue
        base = m["base"]
        if len(base) > 4 and base.endswith(("UP", "DOWN", "BULL", "BEAR")):
            continue  # leveraged tokens
        qv = t.get("quoteVolume") or 0
        if qv >= uni["min_quote_volume_24h"]:
            rows.append((qv, sym))
    rows.sort(reverse=True)
    return [s for _, s in rows[: uni["top_n"]]]


def build_universe_or_fallback(ex, engine, exchange_name: str, timeframe: str,
                               log=None) -> list[str]:
    """For the DAILY job only (not scripts/backfill.py, which should stay
    strict). A live ticker fetch can legitimately come back empty -- a quiet
    liquidity moment, a transient exchange hiccup -- and halting the whole
    day over that is worse than trading yesterday's known-good universe with
    a clear warning logged. scripts/build_dataset.py and train_model.py are
    unaffected; they read whatever is already in the DB either way."""
    symbols = build_universe(ex)
    if symbols:
        return symbols

    with engine.connect() as conn:
        rows = conn.execute(
            select(distinct(Candle.symbol)).where(
                Candle.exchange == exchange_name, Candle.timeframe == timeframe
            )
        )
        fallback = sorted(r[0] for r in rows)

    if log:
        log.warning(
            "Live universe fetch returned 0 symbols (liquidity filter or "
            "exchange hiccup). Falling back to %d previously-stored symbol(s). "
            "If this repeats, check config/settings.yaml min_quote_volume_24h.",
            len(fallback),
        )
    return fallback
