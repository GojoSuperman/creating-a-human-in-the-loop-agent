import pytest

from agent.rules import COMBOS, evaluate, spread
from tests.helpers import mk_item, mk_j

ITEM = mk_item("20001", price=2.0)          # mean8 = 10.0


def rules_of(flags):
    return [f["rule"] for f in flags]


def test_no_flags_for_ordinary_order():
    assert evaluate(ITEM, mk_j(10), [mk_j(10)], ["C1:200", "C2", "C3", "C4"]) == []


def test_c1_amount_strictly_greater():
    assert evaluate(ITEM, mk_j(50), [], ["C1:100"]) == []            # £100 은 초과 아님
    f = evaluate(ITEM, mk_j(51), [], ["C1:100"])
    assert rules_of(f) == ["C1:100"] and "£102" in f[0]["text"]


def test_c2_twice_mean():
    assert evaluate(ITEM, mk_j(20), [], ["C2"]) == []
    assert rules_of(evaluate(ITEM, mk_j(21), [], ["C2"])) == ["C2"]


def test_c3_volatility():
    wild = mk_item("20002", hist=(0, 40, 0, 1, 0, 30, 0, 2))
    assert rules_of(evaluate(wild, mk_j(5), [], ["C3"])) == ["C3"]
    assert evaluate(ITEM, mk_j(5), [], ["C3"]) == []


@pytest.mark.parametrize("signal,hit", [("평소", False), ("증가", False), ("급증", True), ("감소", True)])
def test_c4_signal(signal, hit):
    assert bool(evaluate(ITEM, mk_j(10, signal), [], ["C4"])) is hit


def test_c5_spread_and_single_sample_not_applicable():
    assert spread([mk_j(10)]) is None
    assert evaluate(ITEM, mk_j(10), [mk_j(10)], ["C5"]) == []
    assert spread([mk_j(10), mk_j(12), mk_j(13)]) == pytest.approx(0.25)
    assert evaluate(ITEM, mk_j(10), [mk_j(10), mk_j(12), mk_j(13)], ["C5"]) == []
    assert rules_of(evaluate(ITEM, mk_j(10), [mk_j(10), mk_j(14), mk_j(12)], ["C5"])) == ["C5"]
    assert spread([mk_j(0), mk_j(0), mk_j(3)]) == 1.0            # 중앙값 0 → max>0 이면 참


def test_failure_always_stops_even_with_empty_combo():
    f = evaluate(ITEM, {"error": "timeout"}, [], [])
    assert rules_of(f) == ["F"]


def test_all_stops_everything():
    assert rules_of(evaluate(ITEM, mk_j(1), [], ["ALL"])) == ["ALL"]


def test_unknown_rule_raises():
    with pytest.raises(ValueError):
        evaluate(ITEM, mk_j(1), [], ["C9"])


def test_combos_match_spec_order():
    assert [c for _, c in COMBOS] == [
        [], ["C1:100"], ["C1:200"], ["C1:300"], ["C1:200", "C2"], ["C1:200", "C2", "C3"],
        ["C1:200", "C2", "C4"], ["C1:200", "C2", "C4", "C5"], ["ALL"]]
