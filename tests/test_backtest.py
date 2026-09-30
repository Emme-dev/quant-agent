"""Backtest tests use synthetic data -- no lightgbm needed -- so they run
fast and check the mechanics (costs, turnover, no-trade-no-cost, metrics
math) in isolation from model quality."""
import numpy as np
import pandas as pd
import pytest

from quantagent.backtest.costs import apply_costs
from quantagent.backtest.metrics import sharpe_ratio, max_drawdown, summarize
from quantagent.backtest.engine import run_backtest
from quantagent.strategy.daily_rank import DailyRankStrategy


def test_apply_costs_basic():
    # full rebalance (turnover=1), 10bps fee + 5bps slippage -> 0.15%
    assert apply_costs(1.0, 10, 5) == pytest.approx(0.0015)
    assert apply_costs(0.0, 10, 5) == 0.0


def test_max_drawdown_on_known_curve():
    curve = pd.Series([100, 120, 90, 95, 130])
    # trough 90 from peak 120 -> -25%
    assert max_drawdown(curve) == pytest.approx(-0.25)


def test_sharpe_zero_when_flat():
    flat = pd.Series([0.0] * 30)
    assert sharpe_ratio(flat) == 0.0


def _make_oos(n_days=20, symbols=("A", "B", "C", "D")):
    dates = pd.date_range("2025-01-01", periods=n_days)
    rows = []
    rng = np.random.default_rng(0)
    for d in dates:
        for i, s in enumerate(symbols):
            # symbol A always has the highest score AND the highest realized
            # return -> a perfect strategy should clearly beat the benchmark
            score = len(symbols) - i + rng.normal(0, 0.01)
            ret = 0.02 - i * 0.01 + rng.normal(0, 0.001)
            rows.append({"date": d, "symbol": s, "score": score, "target_ret_1d": ret})
    return pd.DataFrame(rows)


def test_strategy_with_real_signal_beats_benchmark():
    oos = _make_oos()
    result = run_backtest(oos, DailyRankStrategy(top_k=1), "target_ret_1d",
                          fee_bps=1, slippage_bps=1)
    assert result["strategy_metrics"]["final_equity"] > result["benchmark_metrics"]["final_equity"]


def test_no_turnover_cost_when_holdings_unchanged():
    """Same top-1 symbol every day -> turnover should be 1.0 only on day one
    (entering from flat) and ~0 every day after."""
    dates = pd.date_range("2025-01-01", periods=5)
    rows = [{"date": d, "symbol": "A", "score": 1.0, "target_ret_1d": 0.01} for d in dates]
    rows += [{"date": d, "symbol": "B", "score": 0.0, "target_ret_1d": -0.01} for d in dates]
    oos = pd.DataFrame(rows)
    result = run_backtest(oos, DailyRankStrategy(top_k=1), "target_ret_1d",
                          fee_bps=10, slippage_bps=5)
    turns = result["sim"]["turnover"].tolist()
    assert turns[0] == pytest.approx(1.0)
    assert all(t == pytest.approx(0.0) for t in turns[1:])


def test_costs_reduce_equity_relative_to_zero_cost():
    oos = _make_oos()
    cheap = run_backtest(oos, DailyRankStrategy(top_k=1), "target_ret_1d", 0, 0)
    pricey = run_backtest(oos, DailyRankStrategy(top_k=1), "target_ret_1d", 50, 50)
    assert pricey["strategy_metrics"]["final_equity"] < cheap["strategy_metrics"]["final_equity"]


def test_summarize_keys_present():
    curve = pd.Series([100, 101, 99, 103])
    rets = curve.pct_change()
    m = summarize(curve, rets)
    for k in ("sharpe", "cagr", "max_drawdown", "final_equity", "n_days"):
        assert k in m
