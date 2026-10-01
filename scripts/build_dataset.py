"""Day 2 entry point: python scripts/build_dataset.py
Builds features + targets for the stored universe and writes a parquet file."""
from quantagent.core.config import settings
from quantagent.core.db import engine
from quantagent.core.logging import get_logger
from quantagent.data.exchange import make_exchange
from quantagent.data.universe import build_universe
from quantagent.features.build import build_features_for_universe, FEATURE_COLUMNS
from quantagent.features.targets import make_training_table

log = get_logger("build_dataset")


def main():
    cfg = settings()
    ex = make_exchange(cfg["exchange"])
    symbols = build_universe(ex)
    log.info("Building features for %d symbols", len(symbols))

    feat = build_features_for_universe(engine(), cfg["exchange"], symbols, cfg["timeframe"])
    if feat.empty:
        log.warning("No candles found. Run scripts/backfill.py first.")
        return

    horizon = 1
    table = make_training_table(feat, FEATURE_COLUMNS, horizon=horizon)
    out_path = "data/training_table.parquet"
    table.to_parquet(out_path, index=False)
    log.info("Wrote %d rows, %d symbols -> %s", len(table), table["symbol"].nunique(), out_path)
    log.info("Target class balance:\n%s",
             table[f"target_class_{horizon}b"].value_counts(normalize=True))


if __name__ == "__main__":
    main()
