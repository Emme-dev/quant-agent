"""Day 3 entry point: python scripts/train_model.py
Reads data/training_table.parquet (from scripts/build_dataset.py), runs
walk-forward validation, prints fold metrics, and saves the final model."""
import pandas as pd
from quantagent.core.logging import get_logger
from quantagent.features.build import FEATURE_COLUMNS
from quantagent.ml.train import train_walk_forward
from quantagent.ml.registry import save_model

log = get_logger("train_model")

TARGET_COL = "target_ret_1d"


def main():
    table = pd.read_parquet("data/training_table.parquet")
    table["date"] = pd.to_datetime(table["date"])
    log.info("Loaded %d rows, %d symbols, %s -> %s",
             len(table), table["symbol"].nunique(),
             table["date"].min().date(), table["date"].max().date())

    n_dates = table["date"].nunique()
    # Scale validation windows to however much history is actually available,
    # so this also works on a small first backfill instead of hard erroring.
    min_train_days = max(30, min(180, n_dates - 30))
    test_days = max(5, min(30, (n_dates - min_train_days) // 3 or 5))

    result = train_walk_forward(table, FEATURE_COLUMNS, TARGET_COL,
                                n_splits=5, min_train_days=min_train_days,
                                test_days=test_days)

    for m in result["folds"]:
        log.info("fold test %s..%s | n=%d mae=%.5f rmse=%.5f dir_acc=%.3f",
                 m["test_start_date"], m["test_end_date"], m["n_test"],
                 m["mae"], m["rmse"], m["direction_accuracy"])

    if not result["folds"]:
        log.warning("No folds produced -- not enough history yet. "
                    "Backfill more days, then retry.")
        return

    version = save_model(result["final_model"], FEATURE_COLUMNS, result["folds"],
                         extra_meta={"target_col": TARGET_COL})
    log.info("Saved model version %s", version)


if __name__ == "__main__":
    main()
