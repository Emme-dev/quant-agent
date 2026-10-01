"""Risk rule tests. Pure functions, no DB, no lightgbm -- these are the
checks that matter most since they're the last line of defense before an
order is placed."""
import pytest

from quantagent.risk.rules import (cap_position_size, cap_gross_exposure,
                                    check_daily_loss_limit, apply_risk_rules)
from quantagent.risk.sizing import weights_to_orders


def test_cap_position_size_clips_without_redistributing():
    weights = {"A": 0.25, "B": 0.05}
    capped, adj = cap_position_size(weights, max_position_pct=0.10)
    assert capped == {"A": 0.10, "B": 0.05}
    assert len(adj) == 1  # only A was adjusted


def test_cap_gross_exposure_scales_proportionally():
    weights = {"A": 0.4, "B": 0.4}  # gross 0.8
    scaled, adj = cap_gross_exposure(weights, max_gross_exposure_pct=0.6)
    assert sum(scaled.values()) == pytest.approx(0.6)
    assert scaled["A"] == pytest.approx(scaled["B"])  # ratio preserved
    assert len(adj) == 1


def test_cap_gross_exposure_noop_when_already_within_limit():
    weights = {"A": 0.1, "B": 0.1}
    scaled, adj = cap_gross_exposure(weights, max_gross_exposure_pct=0.6)
    assert scaled == weights
    assert adj == []


def test_daily_loss_limit_triggers_at_threshold():
    assert check_daily_loss_limit(1000, 970, 0.03) is True   # exactly -3%
    assert check_daily_loss_limit(1000, 971, 0.03) is False  # -2.9%
    assert check_daily_loss_limit(1000, 1050, 0.03) is False  # a gain


def test_apply_risk_rules_halts_on_config_kill_switch():
    cfg = {"kill_switch": True, "max_position_pct": 1.0,
           "max_gross_exposure_pct": 1.0, "daily_loss_limit_pct": 0.03}
    d = apply_risk_rules({"A": 0.5}, 1000, 1000, cfg)
    assert d.trading_halted is True
    assert d.weights == {}


def test_apply_risk_rules_halts_on_loss_limit_and_ignores_weights():
    cfg = {"kill_switch": False, "max_position_pct": 1.0,
           "max_gross_exposure_pct": 1.0, "daily_loss_limit_pct": 0.03}
    d = apply_risk_rules({"A": 0.5}, 1000, 950, cfg)  # -5% > 3% limit
    assert d.trading_halted is True
    assert "loss limit" in d.halt_reason


def test_apply_risk_rules_normal_path_applies_both_caps():
    cfg = {"kill_switch": False, "max_position_pct": 0.10,
           "max_gross_exposure_pct": 0.15, "daily_loss_limit_pct": 0.03}
    d = apply_risk_rules({"A": 0.3, "B": 0.3}, 1000, 1000, cfg)
    assert d.trading_halted is False
    assert max(d.weights.values()) <= 0.10 + 1e-9
    assert sum(d.weights.values()) <= 0.15 + 1e-9


def test_weights_to_orders_buys_to_reach_target():
    orders = weights_to_orders({"A": 0.5}, equity=1000, prices={"A": 100},
                               current_positions={})
    assert len(orders) == 1
    assert orders[0] == {"symbol": "A", "side": "buy", "qty": 5.0, "price": 100}


def test_weights_to_orders_sells_when_reducing():
    orders = weights_to_orders({"A": 0.1}, equity=1000, prices={"A": 100},
                               current_positions={"A": 5.0})
    assert orders[0]["side"] == "sell"
    assert orders[0]["qty"] == pytest.approx(4.0)


def test_weights_to_orders_closes_position_not_in_target():
    orders = weights_to_orders({}, equity=1000, prices={"B": 50},
                               current_positions={"B": 2.0})
    assert orders == [{"symbol": "B", "side": "sell", "qty": 2.0, "price": 50}]


def test_weights_to_orders_skips_dust():
    orders = weights_to_orders({"A": 0.0001}, equity=1000, prices={"A": 100},
                               current_positions={}, dust_notional=1.0)
    assert orders == []
