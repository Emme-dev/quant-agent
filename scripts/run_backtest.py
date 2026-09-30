"""Day 4 entry point: python scripts/run_backtest.py
Collects out-of-sample (walk-forward) predictions, runs the daily-rank
strategy through the backtest engine with fees + slippage, and prints
strategy vs. buy-and-hold benchmark metrics."""
import pandas as pd
from quantagent.core.logging import get_logger
from quantagent.features.build import FEATURE_COLUMNS
from quantagent.ml.train import collect_oos_predictions
from quantagent.backtest.engine import run_backtest
from quantagent.strategy.daily_rank import DailyRankStrategy

log = get_logger("run_backtest")
TARGET_COL = "target_ret_1d"


def main():
    table = pd.read_parquet("data/training_table.parquet")
    table["date"] = pd.to_datetime(table["date"])

    n_dates = table["date"].nunique()
    min_train_days = max(30, min(180, n_dates - 30))
    test_days = max(5, min(30, (n_dates - min_train_days) // 3 or 5))

    log.info("Collecting out-of-sample predictions (this retrains per fold)...")
    oos = collect_oos_predictions(table, FEATURE_COLUMNS, TARGET_COL,
                                  n_splits=5, min_train_days=min_train_days,
                                  test_days=test_days)
    if oos.empty:
        log.warning("No out-of-sample predictions produced -- not enough history yet.")
        return
    log.info("OOS predictions: %d rows, %s -> %s",
             len(oos), oos["date"].min().date(), oos["date"].max().date())

    result = run_backtest(oos, DailyRankStrategy(top_k=3), TARGET_COL,
                          fee_bps=10, slippage_bps=5)

    sm, bm = result["strategy_metrics"], result["benchmark_metrics"]
    log.info("STRATEGY   sharpe=%.2f cagr=%.1f%% max_dd=%.1f%% final=$%.0f avg_turnover=%.2f",
             sm["sharpe"], sm["cagr"] * 100, sm["max_drawdown"] * 100,
             sm["final_equity"], sm["avg_turnover"])
    log.info("BENCHMARK  sharpe=%.2f cagr=%.1f%% max_dd=%.1f%% final=$%.0f (equal-weight, no costs)",
             bm["sharpe"], bm["cagr"] * 100, bm["max_drawdown"] * 100, bm["final_equity"])

    result["sim"].to_csv("data/backtest_daily.csv", index=False)
    log.info("Wrote day-by-day detail to data/backtest_daily.csv")


if __name__ == "__main__":
    main()
