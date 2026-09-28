"""API + 정적 화면. 실행: uvicorn server.app:create_app --factory"""
import asyncio
import json
import threading
import time
import uuid
from collections import Counter
from pathlib import Path

from fastapi import Body, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from agent.batch_graph import BatchCtx, cached_judge_fn, run_batch
from agent.judge import OpenAILLM, judge_item
from agent.order_graph import (NotPending, OrderCtx, build_order_graph, decide, review_payload,
                               start_order)
from agent.settings import (DATA_WEEKS, ROOT, RUNS, SESSION_TTL_HOURS, STALE_HOURS, checkpoint_url,
                            load_env, store_url)
from agent.store import Store, make_checkpointer
from server.events import EventBus

DEFAULT_COMBO = ["C1:200", "C2", "C4"]    # runs/selected.json 이 생기기 전 개발용
WAITING = ("pending", "failed_to_human")


def create_app(store_url_=None, checkpoint_url_=None, runs_dir=RUNS, weeks_dir=DATA_WEEKS,
               web_dir=ROOT / "web", sync_runs=False):
    load_env()
    runs_dir, weeks_dir = Path(runs_dir), Path(weeks_dir)
    store = Store(store_url_ or store_url())
    saver = make_checkpointer(checkpoint_url_ or checkpoint_url())
    graph = build_order_graph(saver)
    bus = EventBus()
    sel = runs_dir / "selected.json"
    combo = json.loads(sel.read_text(encoding="utf-8"))["combo"] if sel.exists() else DEFAULT_COMBO

    app = FastAPI(title="재고 발주 결재")
    app.state.store, app.state.graph, app.state.combo = store, graph, combo

    def cfg(tid):
        return {"configurable": {"thread_id": tid}}

    def weeks():
        return sorted(p.parent.name for p in runs_dir.glob("*/judgments.json"))

    def need_session(sid):
        if not sid or not store.session_exists(sid):
            raise HTTPException(401, "세션이 없습니다. 새로고침해 주세요")
        return sid

    def own(sid, tid):
        if not tid.startswith(sid + ":"):
            raise HTTPException(403, "다른 세션의 발주 건입니다")

    def ctx(sid, key=None):
        return OrderCtx(store=store, llm=OpenAILLM(key) if key else None,
                        emit=lambda e: bus.publish(sid, e))

    def age(created_at):
        a = (time.time() - created_at) / 3600
        return round(a, 1), a > STALE_HOURS

    def cleanup():
        for sid in store.old_sessions(SESSION_TTL_HOURS):
            for tid in store.delete_session(sid):
                saver.delete_thread(tid)

    @app.post("/api/session")
    def new_session():
        cleanup()
        sid = uuid.uuid4().hex[:12]
        store.create_session(sid)
        return {"session": sid, "weeks": weeks(), "combo": combo}

    @app.get("/api/session-info")
    def session_info(x_session: str | None = Header(None)):
        return {"session": need_session(x_session), "weeks": weeks(), "combo": combo}

    @app.post("/api/run")
    def run(body: dict = Body(...), x_session: str | None = Header(None),
            x_openai_key: str | None = Header(None)):
        sid = need_session(x_session)
        week = str(body.get("week", ""))
        path = weeks_dir / f"{week}.json"
        if not path.exists():
            raise HTTPException(404, "없는 주입니다")
        if store.orders(sid, week):
            raise HTTPException(409, "이미 처리한 주입니다. '처음부터'를 눌러 초기화하세요")
        items = json.loads(path.read_text(encoding="utf-8"))["items"]
        if body.get("live"):
            if not x_openai_key:
                raise HTTPException(400, "라이브 실행에는 OpenAI 키가 필요합니다")
            llm = OpenAILLM(x_openai_key)
            judge_fn = lambda it: [judge_item(it, llm)]
        else:
            jp = runs_dir / week / "judgments.json"
            if not jp.exists():
                raise HTTPException(404, "이 주의 녹화된 판단이 없습니다")
            judge_fn = cached_judge_fn(json.loads(jp.read_text(encoding="utf-8")))
        octx = ctx(sid, x_openai_key)
        bctx = BatchCtx(judge_fn=judge_fn, emit=octx.emit,
                        on_judged=lambda it, ss: start_order(graph, octx, sid, week, it, ss, combo))

        def job():
            try:
                run_batch(week, items, bctx)
                octx.emit({"type": "batch_done", "week": week})
            except Exception as e:           # 화면에 알리고 서버는 살아 있는다
                octx.emit({"type": "batch_error", "week": week, "message": str(e)[:200]})

        if sync_runs:
            job()
        else:
            threading.Thread(target=job, daemon=True).start()
        return JSONResponse({"week": week, "total": len(items)}, status_code=202)

    @app.get("/api/events")
    async def events(request: Request, session: str):
        need_session(session)                 # EventSource 는 헤더를 못 보내서 쿼리로 받는다
        q = bus.subscribe(session)

        async def gen():
            try:
                while not await request.is_disconnected():
                    try:
                        e = await asyncio.wait_for(q.get(), timeout=15)
                    except asyncio.TimeoutError:
                        yield {"event": "ping", "data": "{}"}
                        continue
                    yield {"event": e["type"], "data": json.dumps(e, ensure_ascii=False)}
            finally:
                bus.unsubscribe(session, q)
        return EventSourceResponse(gen())

    @app.get("/api/summary")
    def summary(week: str, x_session: str | None = Header(None)):
        sid = need_session(x_session)
        rows = store.orders(sid, week)
        counts = Counter(r["status"] for r in rows)
        return {"week": week, "total": len(rows), "counts": dict(counts),
                "pending": sum(counts[s] for s in WAITING)}

    @app.get("/api/pending")
    def pending(week: str, x_session: str | None = Header(None)):
        sid = need_session(x_session)
        out = []
        for r in store.orders(sid, week):
            if r["status"] not in WAITING:
                continue
            st = graph.get_state(cfg(r["thread_id"]))
            if st.next != ("review",):        # 판별 기준은 체크포인트 (교재 2강)
                continue
            p = review_payload(st.values)
            hours, stale = age(r["created_at"])
            out.append({k: p[k] for k in ("thread_id", "code", "name_ko", "name_en", "qty",
                                          "amount_gbp", "amount_krw", "error")}
                       | {"flags": [f["rule"] for f in p["flags"]], "age_hours": hours, "stale": stale})
        return {"items": out}

    @app.get("/api/orders/{tid}")
    def order(tid: str, x_session: str | None = Header(None)):
        sid = need_session(x_session)
        own(sid, tid)
        st = graph.get_state(cfg(tid))
        if not st.values:
            raise HTTPException(404, "없는 발주 건입니다")
        row = next((r for r in store.orders(sid) if r["thread_id"] == tid), None)
        hours, stale = age(row["created_at"]) if row else (0.0, False)
        return review_payload(st.values) | {"pending": st.next == ("review",),
                                            "status": st.values.get("status"),
                                            "age_hours": hours, "stale": stale}

    @app.post("/api/orders/{tid}/decision")
    def decision(tid: str, body: dict = Body(...), x_session: str | None = Header(None),
                 x_openai_key: str | None = Header(None)):
        sid = need_session(x_session)
        own(sid, tid)
        if body.get("action") == "redo" and not x_openai_key:
            raise HTTPException(400, "다시 판정은 OpenAI 키를 넣었을 때만 쓸 수 있습니다")
        try:
            return {"status": decide(graph, ctx(sid, x_openai_key), tid, body)}
        except NotPending:
            raise HTTPException(409, "이미 처리됐거나 대기 중인 건이 아닙니다")
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.get("/api/faxlog")
    def faxlog(week: str | None = None, x_session: str | None = Header(None)):
        items = store.fax_list(need_session(x_session))
        for it in items:                      # thread_id = <세션>:<주>:<상품코드>
            _, it["week"], it["code"] = it["thread_id"].split(":", 2)
        return {"items": [it for it in items if week is None or it["week"] == week]}

    @app.get("/api/eval")
    def eval_doc():
        p = runs_dir / "eval.json"
        if not p.exists():
            raise HTTPException(404, "아직 기준 검증을 돌리지 않았습니다")
        return json.loads(p.read_text(encoding="utf-8"))

    @app.post("/api/reset")
    def reset(x_session: str | None = Header(None)):
        sid = need_session(x_session)
        for tid in store.delete_session(sid):
            saver.delete_thread(tid)
        store.create_session(sid)
        return {"ok": True}

    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    return app
