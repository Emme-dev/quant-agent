"""Turns a PipelineResult into a plain-English daily report. Deterministic
templating, NOT an LLM call -- this keeps the report reproducible and
testable, and keeps a model from ever having authority over what gets
reported about trades it didn't size or approve anyway (that stays entirely
in risk/rules.py and strategy/, per the orchestrator). The boundary between
"orchestrator produces structured facts" and "report formats them" is kept
deliberately clean so this function could later be swapped for an
LLM-authored summary of the same PipelineResult without touching any
trading logic."""
from datetime import datetime, timezone

from .types import PipelineResult


def generate_report(result: PipelineResult) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# Daily Report -- {now}", ""]

    if result.halted:
        lines.append(f"**TRADING HALTED.** {result.halt_reason}")
        if result.run_id is not None:
            lines.append(f"\n_Run ID: {result.run_id}_")
        return "\n".join(lines)

    lines.append(f"Timeframe: `{result.timeframe}` | Model: `{result.model_version}` | "
                f"Run ID: {result.run_id}")
    lines.append("")

    lines.append(f"## Universe ({len(result.universe)})")
    lines.append(", ".join(result.universe) or "(none)")
    lines.append("")

    if result.warnings:
        lines.append("## Warnings")
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("## Equity")
    lines.append(f"- Start of day: ${result.equity_start:,.2f}")
    lines.append(f"- Before trading: ${result.equity_before_trade:,.2f}")
    lines.append(f"- After trading: ${result.equity_after_trade:,.2f}")
    if result.equity_start:
        change = result.equity_after_trade - result.equity_start
        pct = change / result.equity_start * 100
        direction = "up" if change >= 0 else "down"
        lines.append(f"- Day-over-day: {direction} ${abs(change):,.2f} ({pct:+.2f}%)")
    lines.append("")

    lines.append("## Top Scored Symbols")
    top5 = sorted(result.scored, key=lambda r: r["score"], reverse=True)[:5]
    if top5:
        for r in top5:
            lines.append(f"- {r['symbol']}: score={r['score']:.4f}, close={r['close']:.4f}")
    else:
        lines.append("(none)")
    lines.append("")

    if result.risk_adjustments:
        lines.append("## Risk Adjustments")
        for a in result.risk_adjustments:
            lines.append(f"- {a}")
        lines.append("")

    lines.append("## Target Weights")
    if result.approved_weights:
        for sym, w in sorted(result.approved_weights.items(), key=lambda x: -x[1]):
            lines.append(f"- {sym}: {w:.1%}")
    else:
        lines.append("(no positions targeted)")
    lines.append("")

    lines.append(f"## Orders ({len(result.fills)})")
    if result.fills:
        for f in result.fills:
            lines.append(f"- {f['side'].upper()} {f['symbol']}: {f['qty']:.6f} @ "
                        f"${f['fill_price']:.4f} (fee ${f['fee']:.2f})")
    else:
        lines.append("No orders placed today (targets already held, or nothing to trade).")

    return "\n".join(lines)
