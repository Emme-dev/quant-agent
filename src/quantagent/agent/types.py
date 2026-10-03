"""Shared, dependency-light types for the agent layer. Deliberately has NO
imports beyond the standard library, so report.py and its tests can use
PipelineResult without pulling in SQLAlchemy/ccxt/lightgbm -- only
orchestrator.py (which actually runs the pipeline) needs those."""
from dataclasses import dataclass, field


@dataclass
class PipelineResult:
    halted: bool = False
    halt_reason: str | None = None
    run_id: int | None = None
    account_id: int | None = None
    timeframe: str | None = None
    universe: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    scored: list[dict] = field(default_factory=list)       # [{symbol, score, close}]
    equity_start: float | None = None
    equity_before_trade: float | None = None
    equity_after_trade: float | None = None
    raw_weights: dict = field(default_factory=dict)
    approved_weights: dict = field(default_factory=dict)
    risk_adjustments: list[str] = field(default_factory=list)
    orders: list[dict] = field(default_factory=list)
    fills: list[dict] = field(default_factory=list)
    model_version: str | None = None
