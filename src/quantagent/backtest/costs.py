"""Trading costs. Every backtest in this repo must charge these, or the
equity curve is fiction: a daily-rebalanced strategy trades a lot, and fees +
slippage are usually what separates a real edge from a paper one."""


def apply_costs(turnover: float, fee_bps: float, slippage_bps: float) -> float:
    """turnover: fraction of portfolio value traded (0..2, since a full
    rebalance from one set of names to another can be up to 2x notional).
    Returns the cost as a fraction of portfolio value, e.g. 0.001 = 0.1%."""
    return turnover * (fee_bps + slippage_bps) / 10_000
