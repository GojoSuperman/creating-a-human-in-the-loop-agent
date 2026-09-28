import os
import uuid

import pytest

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL 없음")


def test_pending_roundtrip_on_postgres():
    from agent.order_graph import OrderCtx, build_order_graph, decide, is_pending, start_order
    from agent.store import Store, make_checkpointer
    from tests.helpers import mk_item, mk_j
    sid = "pg" + uuid.uuid4().hex[:8]
    store = Store(URL)
    store.create_session(sid)
    app = build_order_graph(make_checkpointer(URL))
    ctx = OrderCtx(store=store)
    tid = start_order(app, ctx, sid, "w", mk_item("80001"), [mk_j(150)], ["C1:200"])
    app2 = build_order_graph(make_checkpointer(URL))       # 새 연결 = 재시작
    assert is_pending(app2, tid)
    assert decide(app2, OrderCtx(store=Store(URL)), tid, {"action": "approve"}) == "approved"
    assert len(store.fax_list(sid)) == 1
    for t in store.delete_session(sid):
        app2.checkpointer.delete_thread(t)


def test_survives_closed_connection():
    # 배포 실측(2026-09-28): Neon(pooler) 이 유휴 연결을 닫자("SSL connection has been closed unexpectedly")
    # 이후 모든 요청이 "the connection is closed" 로 500. 앱이 들고 있던 연결이 닫혀도 다음 요청은 살아야 한다.
    # (pooler 주소라 pg_terminate_backend 로는 앱 쪽 연결이 안 끊겨 재현되지 않았다 — 연결을 직접 닫는다)
    from agent.store import Store, make_checkpointer
    store = Store(URL)
    saver = make_checkpointer(URL)
    for conn in _raw_conns(store) + _raw_conns(saver):
        conn.close()
    sid = "pg" + uuid.uuid4().hex[:8]
    store.create_session(sid)                                    # 닫힌 뒤 첫 요청
    assert store.session_exists(sid)
    assert list(saver.list({"configurable": {"thread_id": "none-" + sid}})) == []
    store.delete_session(sid)


def _raw_conns(obj):
    """Store/Saver 가 들고 있는 psycopg 연결(풀이면 풀 안의 연결)을 꺼낸다."""
    c = getattr(obj, "conn", None)
    pool = getattr(obj, "pool", None) or (c if hasattr(c, "_pool") else None)
    if pool is not None:
        return list(pool._pool)
    return [c]
