"""Simulates the strategy day-by-day on OUT-OF-SAMPLE predictions only (see
ml/train.py:collect_oos_predictions). Using in-sample "final_model"
predictions here would let the model grade its own homework -- the backtest
would look great and mean nothing.

Mechanics per day:
  1. strategy.target_weights(today's scores) -> {symbol: weight}
  2. turnover = sum(|new_weight - old_weight|) over the union of symbols
  3. cost = apply_costs(turnover, fee_bps, slippage_bps)
  4. gross portfolio return = sum(weight * that symbol's REALIZED forward return)
  5. net return = gross - cost
  6. equity *= (1 + net return)
"""
import pandas as pd

from .costs import apply_costs
from .metrics import summarize
from ..strategy.base import Strategy


def run_backtest(oos_df: pd.DataFrame, strategy: Strategy, target_col: str,
                 fee_bps: float = 10.0, slippage_bps: float = 5.0,
                 initial_capital: float = 10_000.0) -> dict:
    """oos_df: columns [date, symbol, score, <target_col>], one row per
    (date, symbol), out-of-sample only. Returns equity curve, daily returns,
    turnover series, per-strategy metrics, and a buy-and-hold benchmark."""
    dates = sorted(oos_df["date"].unique())
    prev_weights: dict[str, float] = {}

    records = []
    for d in dates:
        day = oos_df[oos_df["date"] == d]
        weights = strategy.target_weights(day)

        symbols = set(weights) | set(prev_weights)
        turnover = sum(abs(weights.get(s, 0.0) - prev_weights.get(s, 0.0)) for s in symbols)
        cost = apply_costs(turnover, fee_bps, slippage_bps)

        ret_by_symbol = day.set_index("symbol")[target_col]
        gross_ret = sum(w * ret_by_symbol.get(sym, 0.0) for sym, w in weights.items())
        net_ret = gross_ret - cost

        records.append({"date": d, "gross_return": gross_ret, "cost": cost,
                        "net_return": net_ret, "turnover": turnover,
                        "n_positions": len(weights)})
        prev_weights = weights

    sim = pd.DataFrame(records).sort_values("date").reset_index(drop=True)
    sim["equity"] = initial_capital * (1 + sim["net_return"]).cumprod()

    strat_metrics = summarize(sim["equity"], sim["net_return"], sim["turnover"])

    # Benchmark: equal-weight every symbol available that day, no rebalancing
    # cost charged (a buy-and-hold basket is the honest, near-costless comparison).
    bench_ret = oos_df.groupby("date")[target_col].mean().reindex(dates)
    bench_equity = initial_capital * (1 + bench_ret.fillna(0)).cumprod()
    bench_metrics = summarize(bench_equity, bench_ret)

    return {
        "sim": sim,
        "strategy_metrics": strat_metrics,
        "benchmark_equity": bench_equity,
        "benchmark_metrics": bench_metrics,
    }
