import os
os.environ["DATABASE_URL"] = "sqlite://"  # in-memory

from quantagent.core.db import init_db, session_scope
from quantagent.core.models import Candle
from quantagent.data import ingest

DAY = 86_400_000


def fake_fetch(ex, symbol, tf, since):
    start = (since // DAY) * DAY
    return [[start + i * DAY, 1, 2, 0.5, 1.5, 10] for i in range(5)] if since < 10**13 else []


def test_sync_is_idempotent(monkeypatch):
    init_db()
    calls = {"n": 0}

    def fetch(ex, sym, tf, since):
        calls["n"] += 1
        # second call asks for candles after the last stored one: return nothing new
        return fake_fetch(ex, sym, tf, since) if calls["n"] == 1 else []

    monkeypatch.setattr(ingest.exmod, "fetch_ohlcv_all", fetch)
    a = ingest.sync_symbol(None, "x", "BTC/USDT", "1d", 30)
    b = ingest.sync_symbol(None, "x", "BTC/USDT", "1d", 30)
    assert a == 5 and b == 0
    with session_scope() as s:
        assert s.query(Candle).count() == 5
