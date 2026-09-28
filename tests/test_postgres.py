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
