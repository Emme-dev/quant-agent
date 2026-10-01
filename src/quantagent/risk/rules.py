"""Risk rules run on EVERY set of target weights before any order is placed.
This is the layer that keeps a bad model (or a bad day) from doing real
damage -- it must run whether the broker underneath is paper or live."""
from dataclasses import dataclass, field


@dataclass
class RiskDecision:
    weights: dict[str, float]
    adjustments: list[str] = field(default_factory=list)
    trading_halted: bool = False
    halt_reason: str | None = None


def cap_position_size(weights: dict[str, float], max_position_pct: float):
    """No single symbol may exceed max_position_pct of equity. Excess is
    dropped, not redistributed -- redistributing would silently increase
    concentration in whatever's left, defeating the point of the cap."""
    capped, adjustments = {}, []
    for sym, w in weights.items():
        if w > max_position_pct:
            capped[sym] = max_position_pct
            adjustments.append(f"{sym}: {w:.3f} -> {max_position_pct:.3f} (max_position_pct)")
        else:
            capped[sym] = w
    return capped, adjustments


def cap_gross_exposure(weights: dict[str, float], max_gross_exposure_pct: float):
    """Total invested weight may not exceed max_gross_exposure_pct. Scales
    ALL positions down proportionally, so relative sizing is preserved."""
    gross = sum(weights.values())
    if gross <= max_gross_exposure_pct or gross <= 0:
        return weights, []
    scale = max_gross_exposure_pct / gross
    scaled = {s: w * scale for s, w in weights.items()}
    return scaled, [f"scaled all weights x{scale:.3f}: gross {gross:.3f} -> {max_gross_exposure_pct:.3f}"]


def check_daily_loss_limit(equity_start: float, equity_now: float,
                           daily_loss_limit_pct: float) -> bool:
    if equity_start <= 0:
        return False
    loss_pct = (equity_start - equity_now) / equity_start
    return loss_pct >= daily_loss_limit_pct


def apply_risk_rules(raw_weights: dict[str, float], equity_start: float,
                     equity_now: float, risk_cfg: dict) -> RiskDecision:
    """The single entry point execution code should call. Order matters:
    a halt (config kill switch or loss limit) short-circuits before any
    sizing math runs, so a halted day trades absolutely nothing."""
    if risk_cfg.get("kill_switch"):
        return RiskDecision({}, [], True, "kill_switch is set in config/risk.yaml")

    if check_daily_loss_limit(equity_start, equity_now, risk_cfg["daily_loss_limit_pct"]):
        loss_pct = (equity_start - equity_now) / equity_start
        return RiskDecision({}, [], True,
                            f"daily loss limit breached: -{loss_pct:.2%} >= "
                            f"-{risk_cfg['daily_loss_limit_pct']:.2%}")

    weights, adj1 = cap_position_size(raw_weights, risk_cfg["max_position_pct"])
    weights, adj2 = cap_gross_exposure(weights, risk_cfg["max_gross_exposure_pct"])
    return RiskDecision(weights, adj1 + adj2, False, None)
