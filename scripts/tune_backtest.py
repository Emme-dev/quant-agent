"""Quick tuning pass: is the -45% result mostly weak signal, mostly turnover
cost, or both? Tries top_k variations and a slower rebalance (score changes
only trigger a trade every N days) on the SAME out-of-sample predictions
used in run_backtest.py, so results are directly comparable."""
import pandas as pd
from quantagent.core.logging import get_logger
from quantagent.features.build import FEATURE_COLUMNS
from quantagent.ml.train import collect_oos_predictions
from quantagent.backtest.engine import run_backtest
from quantagent.strategy.daily_rank import DailyRankStrategy

log = get_logger("tune_backtest")
TARGET_COL = "target_ret_1d"


class SlowRebalanceStrategy(DailyRankStrategy):
    """Only recompute target weights every `every_n_days` calls; otherwise
    repeat yesterday's weights. Cuts turnover/cost on a noisy daily signal."""
    def __init__(self, top_k=3, every_n_days=3):
        super().__init__(top_k)
        self.every_n_days = every_n_days
        self._call_count = 0
        self._last_weights = {}

    def target_weights(self, day_scores):
        if self._call_count % self.every_n_days == 0:
            self._last_weights = super().target_weights(day_scores)
        self._call_count += 1
        return self._last_weights


def main():
    table = pd.read_parquet("data/training_table.parquet")
    table["date"] = pd.to_datetime(table["date"])
    n_dates = table["date"].nunique()
    min_train_days = max(30, min(180, n_dates - 30))
    test_days = max(5, min(30, (n_dates - min_train_days) // 3 or 5))

    log.info("Collecting out-of-sample predictions once, reusing for all variants...")
    oos = collect_oos_predictions(table, FEATURE_COLUMNS, TARGET_COL,
                                  n_splits=5, min_train_days=min_train_days,
                                  test_days=test_days)

    variants = [
        ("top_k=3, daily (baseline)", DailyRankStrategy(top_k=3)),
        ("top_k=1, daily", DailyRankStrategy(top_k=1)),
        ("top_k=5, daily", DailyRankStrategy(top_k=5)),
        ("top_k=3, rebalance every 3d", SlowRebalanceStrategy(top_k=3, every_n_days=3)),
        ("top_k=1, rebalance every 3d", SlowRebalanceStrategy(top_k=1, every_n_days=3)),
    ]

    bench_printed = False
    for name, strat in variants:
        result = run_backtest(oos, strat, TARGET_COL, fee_bps=10, slippage_bps=5)
        sm = result["strategy_metrics"]
        log.info("%-30s sharpe=%6.2f cagr=%7.1f%% max_dd=%6.1f%% final=$%7.0f avg_turnover=%.2f",
                 name, sm["sharpe"], sm["cagr"] * 100, sm["max_drawdown"] * 100,
                 sm["final_equity"], sm["avg_turnover"])
        if not bench_printed:
            bm = result["benchmark_metrics"]
            log.info("%-30s sharpe=%6.2f cagr=%7.1f%% max_dd=%6.1f%% final=$%7.0f",
                     "BENCHMARK (equal-weight)", bm["sharpe"], bm["cagr"] * 100,
                     bm["max_drawdown"] * 100, bm["final_equity"])
            bench_printed = True


if __name__ == "__main__":
    main()
