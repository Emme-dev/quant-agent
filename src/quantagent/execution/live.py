"""Real-money broker. Deliberately NOT wired into any script yet -- Day 7's
hardening pass decides when this becomes reachable, and only after testnet
runs and explicit review. Calling this without knowing exactly what you're
doing will place real orders with real funds."""
import ccxt

from ..core.config import settings
from ..core.db import session_scope
from ..core.models import Order, Position
from ..core.vault import get_api_keys
from .broker import Broker


class LiveBroker(Broker):
    def __init__(self, account_id: int, fee_bps: float = 10.0):
        cfg = settings()
        if cfg.get("mode") != "live":
            raise RuntimeError(
                "Refusing to construct LiveBroker: config/settings.yaml mode "
                "is not 'live'. This is a deliberate safeguard, not a bug."
            )
        self.account_id = account_id
        self.fee_bps = fee_bps
        keys = get_api_keys(account_id)
        if not keys.get("apiKey"):
            raise RuntimeError("No exchange API key configured (.env). Refusing to trade live.")
        cls = getattr(ccxt, cfg["exchange"])
        self.ex = cls({"enableRateLimit": True, **keys})

    def get_cash(self) -> float:
        bal = self.ex.fetch_balance()
        return float(bal.get("USDT", {}).get("free", 0.0) or bal.get("USD", {}).get("free", 0.0))

    def get_positions(self) -> dict[str, float]:
        bal = self.ex.fetch_balance()
        return {k: v for k, v in bal.get("total", {}).items() if v}

    def equity(self, prices: dict[str, float]) -> float:
        positions = self.get_positions()
        pos_value = sum(qty * prices.get(sym, 0.0) for sym, qty in positions.items())
        return self.get_cash() + pos_value

    def execute_orders(self, orders: list[dict], run_id: int | None = None) -> list[dict]:
        fills = []
        with session_scope() as s:
            for o in orders:
                result = self.ex.create_order(o["symbol"], "market", o["side"], o["qty"])
                fill_price = result.get("average") or result.get("price") or o["price"]
                s.add(Order(account_id=self.account_id, run_id=run_id, symbol=o["symbol"],
                            side=o["side"], qty=o["qty"], price=fill_price,
                            status=result.get("status", "filled"), is_paper=0))
                fills.append({**o, "fill_price": fill_price, "exchange_order_id": result.get("id")})
        return fills
