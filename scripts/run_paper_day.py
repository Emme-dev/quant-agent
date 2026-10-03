"""Day 5 entry point: python scripts/run_paper_day.py
Thin wrapper around agent/orchestrator.py -- see scripts/run_daily_agent.py
(Day 6) for the fuller version with a saved plain-English report. Kept as a
quick manual-run option with concise console output."""
from quantagent.agent.orchestrator import run_daily_pipeline
from quantagent.core.logging import get_logger

log = get_logger("run_paper_day")


def main():
    result = run_daily_pipeline()

    if result.halted:
        log.error("HALTED: %s", result.halt_reason)
        return

    log.info("Universe (%d): %s", len(result.universe), ", ".join(result.universe))
    for w in result.warnings:
        log.warning(w)
    log.info("Scored %d symbols. Top 3: %s", len(result.scored),
             sorted(result.scored, key=lambda r: -r["score"])[:3])
    log.info("Equity: start_of_day=%.2f current=%.2f",
             result.equity_start, result.equity_before_trade)
    for a in result.risk_adjustments:
        log.info("risk adjustment: %s", a)
    if not result.orders:
        log.info("No orders needed (target weights already held, or nothing to trade).")
    for f in result.fills:
        log.info("FILL %s %s %.6f @ %.2f (fee %.2f)",
                 f["side"], f["symbol"], f["qty"], f["fill_price"], f["fee"])
    log.info("Day complete. Equity: %.2f -> %.2f",
             result.equity_before_trade, result.equity_after_trade)


if __name__ == "__main__":
    main()
