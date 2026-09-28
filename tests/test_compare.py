import json

import pytest

from eval.compare import NeedMoreSamples, baseline, cases, evaluate_all, table
from tests.helpers import mk_item, mk_j

# 단가 2, 평균 10. 실제 판매를 정해 두고 AI 발주량으로 손해를 만든다
A = mk_item("60001")          # AI 150, 실제 10 → 손해 280 → 멈춰야 함, C1·C2 걸림
B = mk_item("60002")          # AI 10, 실제 100 → 손해 180 → 멈춰야 함, 기준에 안 걸림 (놓침)
C = mk_item("60003")          # AI 11, 실제 10 → 손해 2 → 안 멈춰도 됨
D = mk_item("60004")          # 판단 실패
ITEMS = [A, B, C, D]
ACTUAL = {"60001": 10, "60002": 100, "60003": 10, "60004": 10}
SAMPLES = {"60001": [mk_j(150)], "60002": [mk_j(10)], "60003": [mk_j(11)], "60004": [{"error": "x"}]}


def test_cases_labels_and_excludes_failures():
    cs, failed = cases(ITEMS, ACTUAL, SAMPLES, ["C1:200", "C2"])
    assert failed == 1
    by = {c["code"]: c for c in cs}
    assert by["60001"]["stopped"] and by["60001"]["should_stop"]
    assert not by["60002"]["stopped"] and by["60002"]["should_stop"] and by["60002"]["loss"] == 180.0
    assert not by["60003"]["should_stop"]


def test_table_rows_follow_combos():
    t = table(ITEMS, ACTUAL, SAMPLES, combos=[("없음", []), ("C1(£200)+C2", ["C1:200", "C2"])])
    assert [r["name"] for r in t["rows"]] == ["없음", "C1(£200)+C2"]
    assert t["rows"][0]["missed_loss"] == 460.0 and t["rows"][1]["missed_loss"] == 180.0
    assert t["positives"] == 2 and t["failed"] == 1


def test_baseline_compares_llm_to_naive_mean():
    b = baseline(ITEMS, ACTUAL, SAMPLES)
    assert b["llm_loss"] == 280.0 + 180.0 + 2.0
    assert b["naive_loss"] == 0.0 + 180.0 + 0.0


def _write(tmp, week, items, actual, samples, model="m"):
    (tmp / "weeks").mkdir(exist_ok=True)
    (tmp / "weeks" / f"{week}.json").write_text(json.dumps({"week": week, "items": items}), encoding="utf-8")
    (tmp / "weeks" / f"{week}.answers.json").write_text(json.dumps({"week": week, "actual": actual}), encoding="utf-8")
    (tmp / "runs" / week).mkdir(parents=True, exist_ok=True)
    (tmp / "runs" / week / "judgments.json").write_text(json.dumps(
        {"week": week, "model": model, "samples": len(next(iter(samples.values()))), "items": samples}), encoding="utf-8")


def test_evaluate_all_selects_on_dev_and_reports_tests(tmp_path, monkeypatch):
    three = {k: v * 3 for k, v in SAMPLES.items()}
    _write(tmp_path, "dev", ITEMS, ACTUAL, three)
    _write(tmp_path, "t1", ITEMS, ACTUAL, SAMPLES)
    monkeypatch.setattr("eval.compare.DEV_WEEK", "dev")
    monkeypatch.setattr("eval.compare.TEST_WEEKS", ("t1",))
    monkeypatch.setattr("eval.compare.MAX_RATE", 0.5)
    doc = evaluate_all(tmp_path / "weeks", tmp_path / "runs")
    assert len(doc["dev"]["tables"]) == 3
    assert doc["selected"]["combo"] and doc["tests"][0]["week"] == "t1"
    assert json.loads((tmp_path / "runs" / "selected.json").read_text(encoding="utf-8"))["combo"] == doc["selected"]["combo"]
    assert doc["dev"]["spread"]["기준 없음"]["missed_loss"] == [460.0, 460.0]


def test_c5_selected_without_test_samples_raises(tmp_path, monkeypatch):
    three = {k: v * 3 for k, v in SAMPLES.items()}
    _write(tmp_path, "dev", ITEMS, ACTUAL, three)
    _write(tmp_path, "t1", ITEMS, ACTUAL, SAMPLES)
    monkeypatch.setattr("eval.compare.DEV_WEEK", "dev")
    monkeypatch.setattr("eval.compare.TEST_WEEKS", ("t1",))
    monkeypatch.setattr("eval.compare.COMBOS", [("C5만", ["C5"])])
    with pytest.raises(NeedMoreSamples):
        evaluate_all(tmp_path / "weeks", tmp_path / "runs")


def test_amendment_requires_two_content_rules_and_keeps_preregistered(tmp_path, monkeypatch):
    # 과제 요건(기준 2개 이상)을 사전 등록 규칙에 빠뜨려 결과를 본 뒤 보정했다 — 원래 결과도 남긴다
    three = {k: v * 3 for k, v in SAMPLES.items()}
    _write(tmp_path, "dev", ITEMS, ACTUAL, three)
    _write(tmp_path, "t1", ITEMS, ACTUAL, SAMPLES)
    monkeypatch.setattr("eval.compare.DEV_WEEK", "dev")
    monkeypatch.setattr("eval.compare.TEST_WEEKS", ("t1",))
    monkeypatch.setattr("eval.compare.COMBOS", [("C1만", ["C1:200"]), ("C1+C2", ["C1:200", "C2"]),
                                                ("전부", ["ALL"])])
    doc = evaluate_all(tmp_path / "weeks", tmp_path / "runs")
    assert doc["preregistered"]["name"] == "C1만"
    assert doc["selected"]["name"] == "C1+C2" and doc["amendment"]
