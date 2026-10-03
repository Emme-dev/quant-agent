"""Pure tests for agent/report.py -- only depends on agent/types.py, so
these run without touching the DB, exchange, or lightgbm."""
from quantagent.agent.types import PipelineResult
from quantagent.agent.report import generate_report


def test_halted_report_is_short_and_states_reason():
    r = PipelineResult(halted=True, halt_reason="daily loss limit breached", run_id=42)
    report = generate_report(r)
    assert "HALTED" in report
    assert "daily loss limit breached" in report
    assert "42" in report
    # a halted report must not try to render equity/orders it doesn't have
    assert "Orders" not in report


def test_normal_report_contains_all_sections():
    r = PipelineResult(
        halted=False, run_id=7, account_id=1, timeframe="1d", model_version="20260101T000000Z",
        universe=["BTC/USD", "ETH/USD"],
        warnings=["1/2 universe symbol(s) had no usable feature row today: ETH/USD"],
        scored=[{"symbol": "BTC/USD", "score": 0.012, "close": 50000.0}],
        equity_start=10000.0, equity_before_trade=10000.0, equity_after_trade=10050.0,
        approved_weights={"BTC/USD": 0.10},
        risk_adjustments=["BTC/USD: 0.333 -> 0.100 (max_position_pct)"],
        fills=[{"symbol": "BTC/USD", "side": "buy", "qty": 0.0002,
               "fill_price": 50025.0, "fee": 1.00}],
    )
    report = generate_report(r)
    for section in ["Universe", "Warnings", "Equity", "Top Scored Symbols",
                    "Risk Adjustments", "Target Weights", "Orders"]:
        assert f"## {section}" in report, f"missing section: {section}"
    assert "BTC/USD" in report
    assert "20260101T000000Z" in report


def test_equity_direction_shown_correctly_for_gain_and_loss():
    gain = PipelineResult(halted=False, run_id=1, equity_start=1000, equity_before_trade=1000,
                          equity_after_trade=1050, scored=[], approved_weights={})
    loss = PipelineResult(halted=False, run_id=2, equity_start=1000, equity_before_trade=1000,
                          equity_after_trade=950, scored=[], approved_weights={})
    assert "up" in generate_report(gain)
    assert "down" in generate_report(loss)


def test_no_orders_message_when_fills_empty():
    r = PipelineResult(halted=False, run_id=3, equity_start=1000, equity_before_trade=1000,
                       equity_after_trade=1000, scored=[], approved_weights={"A": 0.1},
                       fills=[])
    report = generate_report(r)
    assert "No orders placed today" in report


def test_top_scored_symbols_sorted_and_capped_at_five():
    scored = [{"symbol": f"S{i}/USD", "score": i, "close": 1.0} for i in range(10)]
    r = PipelineResult(halted=False, run_id=4, equity_start=1000, equity_before_trade=1000,
                       equity_after_trade=1000, scored=scored, approved_weights={})
    report = generate_report(r)
    lines = [l for l in report.splitlines() if "/USD: score=" in l]
    assert len(lines) == 5
    assert "S9/USD" in lines[0]  # highest score first
