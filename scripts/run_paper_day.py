"""Day 5 entry point: python scripts/run_paper_day.py
One full simulated trading day: fetch current data -> predict -> risk rules
-> paper broker executes -> everything logged. Safe to run repeatedly; it
only ever touches the paper ledger (data/paper_state.json) and the DB."""
from sqlalchemy import select

from quantagent.core.config import settings, risk
from quantagent.core.db import init_db, session_scope, engine
from quantagent.core.models import Account, Run
from quantagent.core.logging import get_logger
from quantagent.data.exchange import make_exchange
from quantagent.data.universe import build_universe_or_fallback
from quantagent.data.ingest import sync_universe
from quantagent.features.build import build_features_for_universe, FEATURE_COLUMNS
from quantagent.ml.predict import predict_latest
from quantagent.ml.registry import latest_version
from quantagent.strategy.daily_rank import DailyRankStrategy
from quantagent.risk.rules import apply_risk_rules
from quantagent.risk.sizing import weights_to_orders
from quantagent.risk import killswitch
from quantagent.execution.paper import PaperBroker

log = get_logger("run_paper_day")


def _get_or_create_account(session, name: str, mode: str) -> Account:
    acct = session.scalar(select(Account).where(Account.name == name))
    if acct is None:
        acct = Account(name=name, mode=mode)
        session.add(acct)
        session.flush()
    return acct


def main():
    cfg, risk_cfg = settings(), risk()
    init_db()

    if killswitch.is_tripped():
        log.error("Kill switch is TRIPPED: %s", killswitch.reason())
        log.error("No trading will occur. Run scripts/reset_killswitch.py after review.")
        return
    if risk_cfg.get("kill_switch"):
        log.error("kill_switch=true in config/risk.yaml. No trading will occur.")
        return

    if latest_version() is None:
        log.error("No trained model found. Run scripts/train_model.py first.")
        return

    with session_scope() as s:
        account = _get_or_create_account(s, cfg["default_account"], "paper")
        account_id = account.id
        run = Run(account_id=account_id, status="running")
        s.add(run)
        s.flush()
        run_id = run.id

    # 1. Fresh data: sync today's candles, then rebuild features from the DB.
    ex = make_exchange(cfg["exchange"])
    symbols = build_universe_or_fallback(ex, engine(), cfg["exchange"], cfg["timeframe"], log=log)
    log.info("Universe today (%d): %s", len(symbols), ", ".join(symbols) or "(empty)")
    if not symbols:
        log.error("Universe is empty and no fallback symbols exist in the DB either. "
                  "Run scripts/backfill.py first.")
        return
    sync_universe(ex, cfg["exchange"], symbols, cfg["timeframe"], history_days=30)
    feat = build_features_for_universe(engine(), cfg["exchange"], symbols, cfg["timeframe"])
    if feat.empty:
        log.error("No feature data available. Run scripts/backfill.py first.")
        return

    # 2. Predict (writes Signal rows) and pull today's close price per symbol.
    scored = predict_latest(feat, account_id=account_id, run_id=run_id)
    if scored.empty:
        log.warning("No symbols had complete features today -- nothing to trade.")
        return
    prices = dict(zip(scored["symbol"], scored["close"]))
    log.info("Scored %d symbols. Top 3: %s", len(scored),
             scored.head(3)[["symbol", "score"]].to_dict("records"))

    # 3. Broker + day-start equity snapshot (for the daily loss check).
    broker = PaperBroker(account_id, initial_cash=risk_cfg["initial_capital"],
                         fee_bps=risk_cfg["fee_bps"], slippage_bps=risk_cfg["slippage_bps"])
    equity_start = broker.mark_day_start(prices)
    equity_now = broker.equity(prices)
    log.info("Equity: start_of_day=%.2f current=%.2f", equity_start, equity_now)

    # 4. Strategy -> raw weights -> risk rules -> approved weights.
    strategy = DailyRankStrategy(top_k=risk_cfg["top_k"])
    raw_weights = strategy.target_weights(scored)
    decision = apply_risk_rules(raw_weights, equity_start, equity_now, risk_cfg)

    if decision.trading_halted:
        killswitch.trip(decision.halt_reason)
        log.error("TRADING HALTED: %s", decision.halt_reason)
        with session_scope() as s:
            r = s.get(Run, run_id)
            r.status = "halted"
            r.summary = {"reason": decision.halt_reason, "equity": equity_now}
        return

    for a in decision.adjustments:
        log.info("risk adjustment: %s", a)

    # 5. Size and execute.
    orders = weights_to_orders(decision.weights, equity_now, prices, broker.get_positions())
    if not orders:
        log.info("No orders needed (target weights already held, or nothing to trade).")
    else:
        fills = broker.execute_orders(orders, run_id=run_id)
        for f in fills:
            log.info("FILL %s %s %.6f @ %.2f (fee %.2f)",
                     f["side"], f["symbol"], f["qty"], f["fill_price"], f["fee"])

    equity_after = broker.equity(prices)
    with session_scope() as s:
        r = s.get(Run, run_id)
        r.status = "completed"
        r.summary = {"equity_start": equity_start, "equity_before_trade": equity_now,
                    "equity_after_trade": equity_after, "n_orders": len(orders),
                    "weights": decision.weights, "model_version": latest_version()}
    log.info("Day complete. Equity: %.2f -> %.2f", equity_now, equity_after)


if __name__ == "__main__":
    main()
