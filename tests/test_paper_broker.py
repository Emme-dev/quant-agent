"""PaperBroker tests. Uses an in-memory DB (see conftest-style env var, same
pattern as test_ingest.py) and a temp JSON state file so runs never touch a
real data/paper_state.json."""
import os
os.environ.setdefault("DATABASE_URL", "sqlite://")

from quantagent.core.db import init_db
from quantagent.execution.paper import PaperBroker


def _broker(tmp_path, cash=1000.0):
    init_db()
    return PaperBroker(account_id=1, initial_cash=cash, fee_bps=10, slippage_bps=5,
                       state_path=tmp_path / "paper_state.json")


def test_buy_reduces_cash_and_adds_position(tmp_path):
    b = _broker(tmp_path)
    orders = [{"symbol": "A", "side": "buy", "qty": 2.0, "price": 100.0}]
    b.execute_orders(orders)
    assert b.get_positions()["A"] == 2.0
    # fill price includes slippage (buy pays UP): 100 * 1.0005 = 100.05
    # notional = 200.1, fee = 200.1 * 0.001 = 0.2001
    assert b.get_cash() < 1000 - 200  # cash dropped by more than raw notional (fee+slippage)


def test_sell_increases_cash_and_removes_dust_position(tmp_path):
    b = _broker(tmp_path)
    b.execute_orders([{"symbol": "A", "side": "buy", "qty": 2.0, "price": 100.0}])
    cash_after_buy = b.get_cash()
    b.execute_orders([{"symbol": "A", "side": "sell", "qty": 2.0, "price": 100.0}])
    assert "A" not in b.get_positions()
    assert b.get_cash() > cash_after_buy


def test_equity_matches_cash_plus_positions_value(tmp_path):
    b = _broker(tmp_path)
    b.execute_orders([{"symbol": "A", "side": "buy", "qty": 2.0, "price": 100.0}])
    eq = b.equity({"A": 110.0})
    assert eq == b.get_cash() + 2.0 * 110.0


def test_state_persists_across_broker_instances(tmp_path):
    path = tmp_path / "paper_state.json"
    init_db()
    b1 = PaperBroker(account_id=1, initial_cash=1000.0, state_path=path)
    b1.execute_orders([{"symbol": "A", "side": "buy", "qty": 1.0, "price": 50.0}])
    b2 = PaperBroker(account_id=1, initial_cash=1000.0, state_path=path)
    assert b2.get_positions() == b1.get_positions()
    assert b2.get_cash() == b1.get_cash()


def test_mark_day_start_is_stable_within_the_same_day(tmp_path):
    b = _broker(tmp_path)
    first = b.mark_day_start({"A": 100.0})
    b.execute_orders([{"symbol": "A", "side": "buy", "qty": 1.0, "price": 100.0}])
    second = b.mark_day_start({"A": 100.0})  # same calendar day
    assert first == second  # snapshot didn't move even though equity changed
