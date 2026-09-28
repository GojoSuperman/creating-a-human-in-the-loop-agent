"""발주 건 그래프 — 한 건의 승인 절차 (스펙 §2.2). thread_id = <세션>:<주>:<상품코드>."""
import threading
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

from agent.judge import AuthFailed, QuotaExceeded, judge_item
from agent.rules import evaluate
from agent.settings import EDIT_MAX_MULT, GBP_KRW, REDO_MAX

ACTIONS = ("approve", "edit", "reject", "redo")


class OrderState(TypedDict, total=False):
    thread_id: str
    session: str
    week: str
    item: dict
    judgment: dict
    samples: list
    combo: list
    flags: list
    decision: dict | None
    redo_count: int
    po: dict
    status: str


@dataclass
class OrderCtx:
    store: Any
    llm: Any = None
    emit: Callable[[dict], None] = lambda e: None


class NotPending(Exception):
    pass


def _cfg(tid):
    return {"configurable": {"thread_id": tid}}


def _ev(state, kind, **extra):
    return {"type": kind, "thread_id": state["thread_id"], "code": state["item"]["code"],
            "week": state["week"], **extra}


def po_text(qty, price):
    amt = qty * price
    return f"거래처에 {qty:,}개, £{amt:,.2f}(₩{round(amt * GBP_KRW):,}) 발주서가 팩스로 발송됩니다"


def review_payload(state):
    item, j = state["item"], state["judgment"]
    qty = j.get("qty")
    left = REDO_MAX - state.get("redo_count", 0)
    options = (["approve"] if qty is not None else []) + ["edit", "reject"] + (["redo"] if left > 0 else [])
    amt = qty * item["price_gbp"] if qty is not None else None
    return {
        "thread_id": state["thread_id"], "code": item["code"], "name_en": item["name_en"],
        "name_ko": j.get("name_ko") or item["name_en"], "price_gbp": item["price_gbp"],
        "hist8": item["hist8"], "mean8": item["mean8"], "qty": qty,
        "amount_gbp": round(amt, 2) if amt is not None else None,
        "amount_krw": round(amt * GBP_KRW) if amt is not None else None,
        "reason_ko": j.get("reason_ko"), "demand_signal": j.get("demand_signal"), "error": j.get("error"),
        "flags": state.get("flags", []),
        "if_approved": po_text(qty, item["price_gbp"]) if qty is not None
        else "AI 판단이 없어 수량을 직접 입력해야 합니다",
        "options": options, "redo_left": left, "redo_count": state.get("redo_count", 0),
    }


def validate_decision(state, d):
    a = d.get("action")
    if a not in ACTIONS:
        raise ValueError("알 수 없는 응답입니다")
    if a == "approve" and state["judgment"].get("qty") is None:
        raise ValueError("AI 판단이 없어 승인할 수 없습니다. 수량을 입력해 주세요")
    if a == "edit":
        q = d.get("qty")
        if not isinstance(q, int) or isinstance(q, bool) or q < 0:
            raise ValueError("수량은 0 이상의 정수여야 합니다")
        cap = EDIT_MAX_MULT * state["item"]["mean8"]
        if q > cap:
            raise ValueError(f"수량은 8주 평균의 {EDIT_MAX_MULT}배({cap:,.0f}개)를 넘을 수 없습니다")
    if a == "reject" and not (isinstance(d.get("reason"), str) and d["reason"].strip()):
        raise ValueError("반려 사유를 글로 적어 주세요")
    if a == "redo":
        if state.get("redo_count", 0) >= REDO_MAX:
            raise ValueError(f"다시 판정은 최대 {REDO_MAX}번입니다")
        if not (isinstance(d.get("instruction"), str) and d["instruction"].strip()):
            raise ValueError("다시 판정 지시를 글로 적어 주세요")
    return d


# ── 노드 ────────────────────────────────────────────────────────────
def check_rules(state):
    return {"flags": evaluate(state["item"], state["judgment"], state.get("samples", []), state["combo"])}


def route_check(state):
    return "enqueue" if state["flags"] else "send_po"


def enqueue(state, runtime: Runtime[OrderCtx]):
    """결재함 투입 알림 — review 밖에 둔다 (resume 때 review 가 처음부터 다시 돌기 때문)."""
    status = "failed_to_human" if "error" in state["judgment"] else "pending"
    runtime.context.store.set_status(state["thread_id"], status)
    runtime.context.emit(_ev(state, "queued", flags=[f["rule"] for f in state["flags"]],
                             texts=[f["text"] for f in state["flags"]], failed=status == "failed_to_human"))
    return {"status": status}


def review(state):
    """interrupt 만 한다. 여기에 부수효과를 두지 않는다."""
    return {"decision": interrupt(review_payload(state))}


def route_review(state):
    return {"approve": "send_po", "edit": "send_po", "reject": "record_reject",
            "redo": "rejudge"}[state["decision"]["action"]]


def send_po(state, runtime: Runtime[OrderCtx]):
    d = state.get("decision") or {}
    item, j = state["item"], state["judgment"]
    qty = d["qty"] if d.get("action") == "edit" else j["qty"]
    status = {"approve": "approved", "edit": "edited"}.get(d.get("action"), "auto_sent")
    by = "human" if d else "auto"
    amt = qty * item["price_gbp"]
    po = {"code": item["code"], "name_en": item["name_en"], "name_ko": j.get("name_ko", ""),
          "qty": qty, "ai_qty": j.get("qty"), "amount_gbp": round(amt, 2),
          "amount_krw": round(amt * GBP_KRW), "by": by, "status": status,
          "redo_count": state.get("redo_count", 0)}
    ctx = runtime.context
    if ctx.store.fax_send(state["thread_id"], state["session"], po):     # 멱등 — 두 번 보내지 않는다
        ctx.emit(_ev(state, "sent", by=by, qty=qty, action=d.get("action")))
    ctx.store.set_status(state["thread_id"], status)
    return {"po": po, "status": status}


def record_reject(state, runtime: Runtime[OrderCtx]):
    ctx = runtime.context
    ctx.store.add_reject(state["thread_id"], state["session"], state["decision"]["reason"].strip())
    ctx.store.set_status(state["thread_id"], "rejected")
    ctx.emit(_ev(state, "rejected", reason=state["decision"]["reason"].strip()[:40]))
    return {"status": "rejected"}


def rejudge(state, runtime: Runtime[OrderCtx]):
    llm = runtime.context.llm
    if llm is None:
        j = {"error": "다시 판정에는 OpenAI 키가 필요합니다"}
    else:
        try:
            j = judge_item(state["item"], llm, state["decision"]["instruction"], state["judgment"])
        except QuotaExceeded:
            j = {"error": "OpenAI 사용 한도 초과"}
        except AuthFailed:
            j = {"error": "OpenAI 키가 올바르지 않습니다"}
    runtime.context.emit(_ev(state, "rejudged", instruction=state["decision"]["instruction"][:40], qty=j.get("qty")))
    return {"judgment": j, "samples": [j], "redo_count": state.get("redo_count", 0) + 1, "decision": None}


def build_order_graph(checkpointer):
    g = StateGraph(OrderState, context_schema=OrderCtx)
    for name, fn in [("check_rules", check_rules), ("enqueue", enqueue), ("review", review),
                     ("send_po", send_po), ("record_reject", record_reject), ("rejudge", rejudge)]:
        g.add_node(name, fn)
    g.add_edge(START, "check_rules")
    g.add_conditional_edges("check_rules", route_check, ["enqueue", "send_po"])
    g.add_edge("enqueue", "review")
    g.add_conditional_edges("review", route_review, ["send_po", "record_reject", "rejudge"])
    g.add_edge("rejudge", "check_rules")
    g.add_edge("send_po", END)
    g.add_edge("record_reject", END)
    return g.compile(checkpointer=checkpointer)


# ── 실행 도우미 ──────────────────────────────────────────────────────
_locks = defaultdict(threading.Lock)
_locks_guard = threading.Lock()


def _lock(tid):
    with _locks_guard:
        return _locks[tid]


def start_order(app, ctx, session, week, item, samples, combo):
    tid = f"{session}:{week}:{item['code']}"
    with _lock(tid):
        st = app.get_state(_cfg(tid))
        if st.values:                              # 이미 시작한 건 — 재실행해도 중복 없음
            if st.next and st.next != ("review",):
                app.invoke(None, _cfg(tid), context=ctx)   # 도중에 죽은 건 — 멈춘 노드부터 이어 간다
            return tid
        if not samples:                            # 이어 가기만 부탁받았는데 시작한 적이 없다 — 할 일 없음
            return tid
        ctx.store.upsert_order(tid, session, week, item["code"], "running")
        app.invoke({"thread_id": tid, "session": session, "week": week, "item": item,
                    "judgment": samples[0], "samples": samples, "combo": combo,
                    "redo_count": 0, "decision": None}, _cfg(tid), context=ctx)
    return tid


def is_pending(app, tid):
    return app.get_state(_cfg(tid)).next == ("review",)


def decide(app, ctx, tid, decision):
    with _lock(tid):                               # 같은 건 동시 결재 → 하나만 통과
        st = app.get_state(_cfg(tid))
        if st.next != ("review",):
            raise NotPending(tid)
        validate_decision(st.values, decision)
        app.invoke(Command(resume=decision), _cfg(tid), context=ctx)
        return app.get_state(_cfg(tid)).values["status"]
