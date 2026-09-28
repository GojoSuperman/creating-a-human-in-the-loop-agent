import subprocess
import sys
import threading

import httpx
import openai
import pytest

from agent.order_graph import (NotPending, OrderCtx, build_order_graph, decide, is_pending,
                               review_payload, start_order, validate_decision)
from agent.store import Store, make_checkpointer
from tests.helpers import FakeLLM, mk_item, mk_j

COMBO = ["C1:200", "C2", "C4"]
ITEM = mk_item("40001", price=2.0)           # mean8 10


@pytest.fixture
def env(tmp_path):
    store = Store(f"sqlite:///{tmp_path}/app.sqlite")
    app = build_order_graph(make_checkpointer(f"sqlite:///{tmp_path}/cp.sqlite"))
    events = []
    ctx = OrderCtx(store=store, emit=events.append)
    return app, store, ctx, events, tmp_path


def run(env, qty=150, signal="평소", llm=None):
    app, store, ctx, events, _ = env
    if llm:
        ctx.llm = llm
    j = mk_j(qty, signal)
    return start_order(app, ctx, "S", "w", ITEM, [j], COMBO)


def test_auto_path_sends_without_human(env):
    app, store, ctx, events, _ = env
    tid = run(env, qty=10)
    assert not is_pending(app, tid)
    st = app.get_state({"configurable": {"thread_id": tid}}).values
    assert st["status"] == "auto_sent" and st["po"]["by"] == "auto"
    assert len(store.fax_list("S")) == 1
    assert [e["type"] for e in events] == ["sent"]


def test_flagged_path_stops_before_fax(env):
    app, store, ctx, events, _ = env
    tid = run(env, qty=150)                    # £300 > £200, 15배 > 2배
    assert is_pending(app, tid)
    assert store.fax_list("S") == []
    assert store.orders("S")[0]["status"] == "pending"
    p = review_payload(app.get_state({"configurable": {"thread_id": tid}}).values)
    assert [f["rule"] for f in p["flags"]] == ["C1:200", "C2"]
    assert p["if_approved"] == "거래처에 150개, £300.00(₩540,000) 발주서가 팩스로 발송됩니다"
    assert p["options"] == ["approve", "edit", "reject", "redo"]


def test_approve_sends_by_human(env):
    app, store, ctx, events, _ = env
    tid = run(env)
    assert decide(app, ctx, tid, {"action": "approve"}) == "approved"
    po = store.fax_list("S")[0]["po"]
    assert po["qty"] == 150 and po["by"] == "human"


def test_edit_sends_edited_qty(env):
    app, store, ctx, events, _ = env
    tid = run(env)
    assert decide(app, ctx, tid, {"action": "edit", "qty": 40}) == "edited"
    po = store.fax_list("S")[0]["po"]
    assert po["qty"] == 40 and po["ai_qty"] == 150


def test_reject_records_reason_and_no_fax(env):
    app, store, ctx, events, _ = env
    tid = run(env)
    assert decide(app, ctx, tid, {"action": "reject", "reason": "재고 충분"}) == "rejected"
    assert store.fax_list("S") == [] and store.rejects("S")[0]["reason"] == "재고 충분"


def test_redo_that_passes_rules_auto_sends(env):
    app, store, ctx, events, _ = env
    tid = run(env, llm=FakeLLM([mk_j(12)]))
    assert decide(app, ctx, tid, {"action": "redo", "instruction": "평소대로"}) == "auto_sent"
    st = app.get_state({"configurable": {"thread_id": tid}}).values
    assert st["redo_count"] == 1 and st["po"]["qty"] == 12


def test_redo_cap_is_two(env):
    app, store, ctx, events, _ = env
    tid = run(env, llm=FakeLLM([mk_j(90)]))    # 재판정해도 C2(90 > 20)에 걸려 다시 결재함으로
    decide(app, ctx, tid, {"action": "redo", "instruction": "다시"})
    decide(app, ctx, tid, {"action": "redo", "instruction": "다시"})
    p = review_payload(app.get_state({"configurable": {"thread_id": tid}}).values)
    assert p["redo_left"] == 0 and "redo" not in p["options"]
    with pytest.raises(ValueError):
        decide(app, ctx, tid, {"action": "redo", "instruction": "또"})


def test_redo_with_failing_llm_returns_to_review(env):
    app, store, ctx, events, _ = env
    bad = openai.AuthenticationError("bad key", response=httpx.Response(
        401, request=httpx.Request("POST", "https://x")), body=None)
    tid = run(env, llm=FakeLLM([bad]))
    decide(app, ctx, tid, {"action": "redo", "instruction": "다시"})
    assert is_pending(app, tid)
    p = review_payload(app.get_state({"configurable": {"thread_id": tid}}).values)
    assert [f["rule"] for f in p["flags"]] == ["F"] and "approve" not in p["options"]
    assert store.orders("S")[0]["status"] == "failed_to_human"


def test_validate_edit_rejects_bad_qty(env):
    app, store, ctx, events, _ = env
    tid = run(env)
    st = app.get_state({"configurable": {"thread_id": tid}}).values
    for q in (-1, "abc", 10.5, True, 101):     # 101 > 평균 10 × 10
        with pytest.raises(ValueError):
            validate_decision(st, {"action": "edit", "qty": q})
    with pytest.raises(ValueError):
        validate_decision(st, {"action": "reject", "reason": "  "})
    with pytest.raises(ValueError):
        validate_decision(st, {"action": "launch"})
    assert is_pending(app, tid)


def test_decide_on_finished_raises_not_pending(env):
    app, store, ctx, events, _ = env
    tid = run(env)
    decide(app, ctx, tid, {"action": "approve"})
    with pytest.raises(NotPending):
        decide(app, ctx, tid, {"action": "approve"})
    assert len(store.fax_list("S")) == 1


def test_concurrent_double_approve(env):
    app, store, ctx, events, _ = env
    tid = run(env)
    results = []

    def go():
        try:
            results.append(decide(app, ctx, tid, {"action": "approve"}))
        except NotPending:
            results.append("409")
    ts = [threading.Thread(target=go) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(results) == ["409", "approved"] and len(store.fax_list("S")) == 1


def test_queued_event_emitted_once_across_resume(env):
    # 교재 2강 함정: resume 하면 review 가 처음부터 다시 돈다 → 알림이 review 안에 있으면 두 번 나간다
    app, store, ctx, events, _ = env
    tid = run(env)
    decide(app, ctx, tid, {"action": "approve"})
    assert [e["type"] for e in events] == ["queued", "sent"]


def test_start_order_twice_is_noop(env):
    app, store, ctx, events, _ = env
    a = run(env, qty=10)
    b = run(env, qty=10)
    assert a == b and len(store.fax_list("S")) == 1


def test_pending_survives_process_restart(env):
    app, store, ctx, events, tmp = env
    tid = run(env)
    code = f"""
from agent.order_graph import OrderCtx, build_order_graph, decide, is_pending
from agent.store import Store, make_checkpointer
app = build_order_graph(make_checkpointer("sqlite:///{tmp}/cp.sqlite"))
ctx = OrderCtx(store=Store("sqlite:///{tmp}/app.sqlite"))
assert is_pending(app, "{tid}")
print(decide(app, ctx, "{tid}", {{"action": "approve"}}))
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "approved"
    assert len(store.fax_list("S")) == 1
