from ..core.config import settings


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
