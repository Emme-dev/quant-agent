"""Day 1 entry point: python scripts/backfill.py"""
from sqlalchemy import select
from quantagent.core.config import settings
from quantagent.core.db import init_db, session_scope
from quantagent.core.models import Account
from quantagent.core.logging import get_logger
from quantagent.data.exchange import make_exchange
from quantagent.data.universe import build_universe
from quantagent.data.ingest import sync_universe

log = get_logger("backfill")


def main():
    cfg = settings()
    init_db()
    with session_scope() as s:
        if not s.scalar(select(Account).where(Account.name == cfg["default_account"])):
            s.add(Account(name=cfg["default_account"], mode=cfg["mode"]))
    ex = make_exchange(cfg["exchange"])  # public data, no keys needed
    symbols = build_universe(ex)
    log.info("Universe (%d): %s", len(symbols), ", ".join(symbols))
    n = sync_universe(ex, cfg["exchange"], symbols, cfg["timeframe"], cfg["history_days"])
    log.info("Done. %d new candles.", n)


if __name__ == "__main__":
    main()
