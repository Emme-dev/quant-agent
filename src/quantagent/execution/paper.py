"""Simulated broker. Cash + positions live in a JSON ledger (data/paper_state.json
by default), deliberately kept OUTSIDE the database so it's a self-contained,
easily-reset simulation -- delete the file and paper trading starts fresh.
Order/Position DB rows are still written on every fill, for the daily report
and for parity with what a live broker would produce."""
import json
from datetime import datetime, timezone
from pathlib import Path

from ..core.db import session_scope
from ..core.logging import get_logger
from ..core.models import Order, Position
from .broker import Broker

log = get_logger("paper_broker")
DEFAULT_STATE_PATH = Path("data/paper_state.json")


class PaperBroker(Broker):
    def __init__(self, account_id: int, initial_cash: float, fee_bps: float = 10.0,
                slippage_bps: float = 5.0, state_path: Path = DEFAULT_STATE_PATH):
        self.account_id = account_id
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps
        self.state_path = state_path
        self.state = self._load_state(initial_cash)

    def _load_state(self, initial_cash: float) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text())
        return {"cash": initial_cash, "positions": {},
                "day_start_equity": None, "day_start_date": None}

    def _save_state(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, indent=2))

    def get_cash(self) -> float:
        return self.state["cash"]

    def get_positions(self) -> dict[str, float]:
        return dict(self.state["positions"])

    def equity(self, prices: dict[str, float]) -> float:
        pos_value = sum(qty * prices.get(sym, 0.0)
                        for sym, qty in self.state["positions"].items())
        return self.state["cash"] + pos_value

    def mark_day_start(self, prices: dict[str, float]) -> float:
        """Call once at the top of a run, before trading. Snapshots today's
        opening equity for the daily-loss-limit check; a second run on the
        same calendar date reuses the same snapshot rather than resetting it,
        so the limit can't be dodged by just running the job again."""
        today = datetime.now(timezone.utc).date().isoformat()
        if self.state.get("day_start_date") != today:
            self.state["day_start_equity"] = self.equity(prices)
            self.state["day_start_date"] = today
            self._save_state()
        return self.state["day_start_equity"]

    def execute_orders(self, orders: list[dict], run_id: int | None = None) -> list[dict]:
        fills = []
        with session_scope() as s:
            for o in orders:
                sym, side, qty, price = o["symbol"], o["side"], o["qty"], o["price"]
                slip = price * (self.slippage_bps / 10_000)
                fill_price = price + slip if side == "buy" else price - slip
                notional = qty * fill_price
                fee = notional * (self.fee_bps / 10_000)

                if side == "buy":
                    self.state["cash"] -= (notional + fee)
                    self.state["positions"][sym] = self.state["positions"].get(sym, 0.0) + qty
                else:
                    self.state["cash"] += (notional - fee)
                    new_qty = self.state["positions"].get(sym, 0.0) - qty
                    if abs(new_qty) < 1e-9:
                        self.state["positions"].pop(sym, None)
                    else:
                        self.state["positions"][sym] = new_qty

                s.add(Order(account_id=self.account_id, run_id=run_id, symbol=sym,
                            side=side, qty=qty, price=fill_price, status="filled",
                            is_paper=1))

                pos = s.query(Position).filter_by(
                    account_id=self.account_id, symbol=sym).one_or_none()
                new_qty = self.state["positions"].get(sym, 0.0)
                if pos is None:
                    s.add(Position(account_id=self.account_id, symbol=sym,
                                   qty=new_qty, avg_price=fill_price))
                else:
                    pos.qty = new_qty
                    pos.avg_price = fill_price  # simplified: last fill, not true VWAP

                fills.append({**o, "fill_price": fill_price, "fee": fee})
        self._save_state()
        log.info("Executed %d order(s). Cash=%.2f", len(orders), self.state["cash"])
        return fills
