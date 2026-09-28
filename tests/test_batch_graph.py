import json

import httpx
import openai
import pytest

from agent.batch_graph import (BatchCtx, JudgmentCache, analyst_of, cached_judge_fn, live_judge_fn,
                               run_batch)
from agent.judge import AuthFailed, QuotaExceeded
from tests.helpers import FakeLLM, mk_item, mk_j

ITEMS = [mk_item(f"5{i:04d}") for i in range(12)]


def test_fan_out_judges_every_item_and_reports():
    seen, events = [], []
    ctx = BatchCtx(judge_fn=lambda it: [mk_j(10)], on_judged=lambda it, ss: seen.append(it["code"]),
                   emit=events.append)
    out = run_batch("w", ITEMS, ctx, concurrency=4)
    assert set(out) == {it["code"] for it in ITEMS} and sorted(seen) == sorted(out)
    assert [e["type"] for e in events].count("judged") == 12
    assert all(0 <= e["analyst"] <= 2 for e in events)


def test_analyst_is_stable():
    assert analyst_of("85123A") == analyst_of("85123A")


def test_live_cache_writes_and_resumes_without_calls(tmp_path):
    path = tmp_path / "w" / "judgments.json"
    llm = FakeLLM([mk_j(7)])
    cache = JudgmentCache(path, "w", "m", samples=2)
    run_batch("w", ITEMS, BatchCtx(judge_fn=live_judge_fn(llm, cache, 2)))
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["model"] == "m" and len(doc["items"]) == 12
    assert all(len(v) == 2 for v in doc["items"].values()) and len(llm.calls) == 24
    llm2 = FakeLLM([mk_j(7)])
    cache2 = JudgmentCache(path, "w", "m", samples=2)
    run_batch("w", ITEMS, BatchCtx(judge_fn=live_judge_fn(llm2, cache2, 2)))
    assert llm2.calls == []


def test_cache_refuses_model_mismatch(tmp_path):
    path = tmp_path / "judgments.json"
    JudgmentCache(path, "w", "m1", 1).put("x", [mk_j(1)])
    with pytest.raises(ValueError):
        JudgmentCache(path, "w", "m2", 1)


def test_quota_stops_and_keeps_finished(tmp_path):
    quota = openai.RateLimitError("q", response=httpx.Response(
        429, request=httpx.Request("POST", "https://x")), body={"code": "insufficient_quota"})
    llm = FakeLLM([mk_j(1)] * 4 + [quota])
    cache = JudgmentCache(tmp_path / "j.json", "w", "m", 1)
    with pytest.raises(QuotaExceeded):
        run_batch("w", ITEMS, BatchCtx(judge_fn=live_judge_fn(llm, cache, 1)), concurrency=1)
    assert len(cache.doc["items"]) == 4


def test_cached_judge_fn_replays():
    doc = {"items": {"a": [mk_j(3)]}}
    assert cached_judge_fn(doc)({"code": "a"})[0]["qty"] == 3


def test_bad_key_aborts_batch_and_caches_nothing(tmp_path):
    bad = openai.AuthenticationError("bad", response=httpx.Response(
        401, request=httpx.Request("POST", "https://x")), body=None)
    cache = JudgmentCache(tmp_path / "j.json", "w", "m", 1)
    with pytest.raises(AuthFailed):
        run_batch("w", ITEMS, BatchCtx(judge_fn=live_judge_fn(FakeLLM([bad]), cache, 1)), concurrency=1)
    assert cache.doc["items"] == {} and not (tmp_path / "j.json").exists()


def test_judged_event_carries_what_the_analyst_says():
    # 사무실 말풍선용 — 분석가가 무엇을 판단했는지
    events = []
    run_batch("w", ITEMS[:1], BatchCtx(judge_fn=lambda it: [mk_j(30, "급증", "재즈 주소록")], emit=events.append))
    e = next(e for e in events if e["type"] == "judged")
    assert e["name"] == "재즈 주소록" and e["qty"] == 30 and e["signal"] == "급증" and e["reason"]


def test_judged_reason_is_not_cut_short_for_bubbles():
    long = "최근 8주 평균 판매량이 약 12개이나 지난 2주 동안 판매가 줄어 다음 주에도 감소가 예상되어 평소보다 적게 들인다"
    events = []
    j = {**mk_j(12, "감소"), "reason_ko": long}
    run_batch("w", ITEMS[:1], BatchCtx(judge_fn=lambda it: [j], emit=events.append))
    assert next(e for e in events if e["type"] == "judged")["reason"] == long
