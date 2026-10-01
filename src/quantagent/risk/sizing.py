"""Turns approved target weights into concrete orders (symbol, side, qty,
price) given current equity, current prices, and current holdings. Pure
function, no I/O, so it's trivial to unit test."""


def weights_to_orders(weights: dict[str, float], equity: float,
                      prices: dict[str, float],
                      current_positions: dict[str, float],
                      dust_notional: float = 1.0) -> list[dict]:
    orders = []
    for sym, w in weights.items():
        price = prices.get(sym)
        if not price:
            continue
        target_qty = (equity * w) / price
        current_qty = current_positions.get(sym, 0.0)
        delta = target_qty - current_qty
        if abs(delta) * price < dust_notional:
            continue
        orders.append({"symbol": sym, "side": "buy" if delta > 0 else "sell",
                       "qty": abs(delta), "price": price})

    # Close any position no longer in the target weights at all.
    for sym, qty in current_positions.items():
        if sym in weights or abs(qty) < 1e-12:
            continue
        price = prices.get(sym)
        if price:
            orders.append({"symbol": sym, "side": "sell" if qty > 0 else "buy",
                           "qty": abs(qty), "price": price})
    return orders
