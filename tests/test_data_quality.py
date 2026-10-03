"""Pure tests for agent/data_quality.py -- no DB, no network, no lightgbm."""
from quantagent.agent.data_quality import check_universe_coverage


def test_no_warnings_when_full_coverage():
    assert check_universe_coverage(["A", "B", "C"], ["A", "B", "C"]) == []


def test_warns_on_missing_symbols():
    w = check_universe_coverage(["A", "B", "C"], ["A", "B"])
    assert len(w) == 1
    assert "C" in w[0]
    assert "1/3" in w[0]


def test_warns_on_low_coverage_and_missing_together():
    w = check_universe_coverage(["A", "B", "C", "D"], ["A"])
    assert len(w) == 2
    assert any("25%" in x for x in w)


def test_no_warning_on_empty_universe():
    assert check_universe_coverage([], []) == []


def test_custom_coverage_threshold():
    # 2/4 = 50% coverage. Default threshold (0.5) should NOT warn (50% is
    # not < 50%); a stricter threshold should.
    w_default = check_universe_coverage(["A", "B", "C", "D"], ["A", "B"], min_coverage=0.5)
    w_strict = check_universe_coverage(["A", "B", "C", "D"], ["A", "B"], min_coverage=0.6)
    assert not any("worth checking" in x for x in w_default)
    assert any("worth checking" in x for x in w_strict)
