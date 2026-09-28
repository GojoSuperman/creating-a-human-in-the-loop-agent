import httpx
import openai
import pytest

from agent.judge import QuotaExceeded, build_prompt, judge_item, validate
from tests.helpers import FakeLLM, mk_item, mk_j

ITEM = mk_item("30001")      # mean8 = 10


def _err(cls, status, body):
    return cls("x", response=httpx.Response(status, request=httpx.Request("POST", "https://x")), body=body)


def test_prompt_has_history_but_no_answer_field():
    p = build_prompt(ITEM)
    assert "30001" in p and str(ITEM["hist8"]) in p
    assert "actual" not in p and "정답" not in p


def test_prompt_includes_instruction_and_previous_on_redo():
    p = build_prompt(ITEM, instruction="절반만", prev=mk_j(40))
    assert "절반만" in p and "40개" in p


def test_validate_rejects_absurd_qty_and_bad_signal():
    with pytest.raises(ValueError):
        validate(mk_j(101), ITEM)                     # 평균 10 × 10배 초과
    with pytest.raises(Exception):
        validate({**mk_j(5), "demand_signal": "폭발"}, ITEM)
    with pytest.raises(Exception):
        validate({**mk_j(5), "qty": -1}, ITEM)
    assert validate(mk_j(100), ITEM)["qty"] == 100


def test_retry_once_then_success():
    llm = FakeLLM([{"qty": "많이"}, mk_j(12)])
    assert judge_item(ITEM, llm)["qty"] == 12 and len(llm.calls) == 2


def test_two_failures_become_error_not_exception():
    llm = FakeLLM([_err(openai.AuthenticationError, 401, None)])
    j = judge_item(ITEM, llm)
    assert "error" in j and "AuthenticationError" in j["error"] and len(llm.calls) == 2


def test_insufficient_quota_raises_immediately():
    llm = FakeLLM([_err(openai.RateLimitError, 429, {"code": "insufficient_quota"})])
    with pytest.raises(QuotaExceeded):
        judge_item(ITEM, llm)
    assert len(llm.calls) == 1
