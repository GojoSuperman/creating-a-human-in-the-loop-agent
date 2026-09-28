import time

from agent.store import Store, make_checkpointer


def st(tmp_path):
    return Store(f"sqlite:///{tmp_path}/app.sqlite")


def test_fax_send_is_idempotent(tmp_path):
    s = st(tmp_path)
    assert s.fax_send("S:w:1", "S", {"qty": 3}) is True
    assert s.fax_send("S:w:1", "S", {"qty": 999}) is False
    log = s.fax_list("S")
    assert len(log) == 1 and log[0]["po"] == {"qty": 3}


def test_orders_index_and_status(tmp_path):
    s = st(tmp_path)
    assert s.upsert_order("S:w:1", "S", "w", "1", "running") is True
    assert s.upsert_order("S:w:1", "S", "w", "1", "running") is False
    s.set_status("S:w:1", "pending")
    assert [o["status"] for o in s.orders("S", "w")] == ["pending"]
    assert s.orders("OTHER") == []


def test_sessions_cleanup_returns_thread_ids(tmp_path):
    s = st(tmp_path)
    old = time.time() - 25 * 3600
    s.create_session("OLD", now=old)
    s.create_session("NEW")
    s.upsert_order("OLD:w:1", "OLD", "w", "1", "pending", now=old)
    s.fax_send("OLD:w:1", "OLD", {"qty": 1}, now=old)
    s.add_reject("OLD:w:1", "OLD", "사유", now=old)
    assert s.old_sessions(24) == ["OLD"]
    assert s.delete_session("OLD") == ["OLD:w:1"]
    assert not s.session_exists("OLD") and s.session_exists("NEW")
    assert s.fax_list("OLD") == [] and s.rejects("OLD") == []


def test_make_checkpointer_sqlite_roundtrip(tmp_path):
    saver = make_checkpointer(f"sqlite:///{tmp_path}/cp.sqlite")
    assert list(saver.list(None)) == []
