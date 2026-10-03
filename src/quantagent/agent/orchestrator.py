"""Day 6: the daily job, as one reusable function instead of logic copied
across scripts. scripts/run_paper_day.py and scripts/run_daily_agent.py both
call run_daily_pipeline() rather than each having their own copy -- the
build_dataset.py/targets.py naming mismatch earlier in this project happened
BECAUSE logic was duplicated and one copy went stale; this is the fix for
that pattern at the orchestration layer.

This is orchestration code, not an LLM making trading decisions. Sizing and
risk stay entirely in risk/rules.py and risk/sizing.py. An LLM-driven
interface could later call the read-only helpers in agent/tools.py to
explain or answer questions about a day, but nothing here or in tools.py
places an order or changes a risk limit -- that boundary is intentional."""
from sqlalchemy import select

from ..core.config import settings, risk
from ..core.db import init_db, session_scope, engine
from ..core.models import Account, Run
from ..core.logging import get_logger
from ..data.exchange import make_exchange
from ..data.universe import build_universe_or_fallback
from ..data.ingest import sync_universe
from ..features.build import build_features_for_universe
from ..ml.predict import predict_latest
from ..ml.registry import latest_version
from ..strategy.daily_rank import DailyRankStrategy
from ..risk.rules import apply_risk_rules
from ..risk.sizing import weights_to_orders
from ..risk import killswitch
from ..execution.paper import PaperBroker
from .types import PipelineResult
from .data_quality import check_universe_coverage

log = get_logger("orchestrator")


def _get_or_create_account(session, name: str, mode: str) -> Account:
    acct = session.scalar(select(Account).where(Account.name == name))
    if acct is None:
        acct = Account(name=name, mode=mode)
        session.add(acct)
        session.flush()
    return acct


def _finalize_run(run_id: int, result: PipelineResult, status: str):
    with session_scope() as s:
        r = s.get(Run, run_id)
        if r is None:
            return
        r.status = status
        r.summary = {
            "halted": result.halted, "halt_reason": result.halt_reason,
            "equity_start": result.equity_start,
            "equity_before_trade": result.equity_before_trade,
            "equity_after_trade": result.equity_after_trade,
            "n_orders": len(result.orders),
            "approved_weights": result.approved_weights,
            "model_version": result.model_version,
            "warnings": result.warnings,
        }


def run_daily_pipeline(account_name: str | None = None) -> PipelineResult:
    cfg, risk_cfg = settings(), risk()
    account_name = account_name or cfg["default_account"]
    init_db()
    result = PipelineResult(timeframe=cfg["timeframe"])

    # --- pre-flight halts: nothing created yet, nothing to finalize ---
    if killswitch.is_tripped():
        result.halted, result.halt_reason = True, f"kill switch file: {killswitch.reason()}"
        log.error(result.halt_reason)
        return result
    if risk_cfg.get("kill_switch"):
        result.halted, result.halt_reason = True, "kill_switch=true in config/risk.yaml"
        log.error(result.halt_reason)
        return result

    version = latest_version()
    if version is None:
        result.halted = True
        result.halt_reason = "No trained model found. Run scripts/train_model.py first."
        log.error(result.halt_reason)
        return result
    result.model_version = version

    with session_scope() as s:
        account = _get_or_create_account(s, account_name, "paper")
        account_id = account.id
        run = Run(account_id=account_id, status="running")
        s.add(run)
        s.flush()
        run_id = run.id
    result.account_id, result.run_id = account_id, run_id

    # --- data stage ---
    ex = make_exchange(cfg["exchange"])
    symbols = build_universe_or_fallback(ex, engine(), cfg["exchange"], cfg["timeframe"], log=log)
    result.universe = symbols
    if not symbols:
        result.halted = True
        result.halt_reason = ("Universe is empty and no fallback symbols exist in the "
                              "DB either. Run scripts/backfill.py first.")
        log.error(result.halt_reason)
        _finalize_run(run_id, result, status="halted")
        return result

    sync_universe(ex, cfg["exchange"], symbols, cfg["timeframe"], history_days=30)
    feat = build_features_for_universe(engine(), cfg["exchange"], symbols, cfg["timeframe"])
    if feat.empty:
        result.halted = True
        result.halt_reason = "No feature data available. Run scripts/backfill.py first."
        log.error(result.halt_reason)
        _finalize_run(run_id, result, status="halted")
        return result

    # --- predict ---
    scored = predict_latest(feat, account_id=account_id, run_id=run_id, version=version)
    if scored.empty:
        result.halted = True
        result.halt_reason = "No symbols had complete features today -- nothing to trade."
        log.warning(result.halt_reason)
        _finalize_run(run_id, result, status="halted")
        return result

    result.scored = scored[["symbol", "score", "close"]].to_dict("records")
    result.warnings.extend(check_universe_coverage(symbols, list(scored["symbol"])))
    for w in result.warnings:
        log.warning(w)

    # --- equity / day-start snapshot ---
    # DELIBERATE, as of Day 7: this always constructs PaperBroker, never
    # LiveBroker, even if config/settings.yaml has mode: live. Going live is
    # a decision made by EDITING THIS LINE, not by a config flag -- a config
    # value is too easy to flip by accident or copy from an example. See
    # execution/live.py's docstring and the README's "Going live" section
    # for what should happen (testnet run, manual review) before that edit
    # is made.
    prices = dict(zip(scored["symbol"], scored["close"]))
    broker = PaperBroker(account_id, initial_cash=risk_cfg["initial_capital"],
                         fee_bps=risk_cfg["fee_bps"], slippage_bps=risk_cfg["slippage_bps"])
    equity_start = broker.mark_day_start(prices)
    equity_now = broker.equity(prices)
    result.equity_start, result.equity_before_trade = equity_start, equity_now

    # --- strategy -> risk gate ---
    strategy = DailyRankStrategy(top_k=risk_cfg["top_k"])
    raw_weights = strategy.target_weights(scored)
    result.raw_weights = raw_weights
    decision = apply_risk_rules(raw_weights, equity_start, equity_now, risk_cfg)

    if decision.trading_halted:
        killswitch.trip(decision.halt_reason)
        result.halted = True
        result.halt_reason = decision.halt_reason
        log.error("TRADING HALTED: %s", decision.halt_reason)
        _finalize_run(run_id, result, status="halted")
        return result

    result.approved_weights = decision.weights
    result.risk_adjustments = decision.adjustments

    # --- size + execute ---
    orders = weights_to_orders(decision.weights, equity_now, prices, broker.get_positions())
    result.orders = orders
    if orders:
        result.fills = broker.execute_orders(orders, run_id=run_id)

    result.equity_after_trade = broker.equity(prices)
    _finalize_run(run_id, result, status="completed")
    return result
