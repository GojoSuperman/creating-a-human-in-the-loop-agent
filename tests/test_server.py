import json
import time

import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from tests.helpers import mk_item, mk_j

W = "2011-06-06"
ITEMS = [mk_item("70001"), mk_item("70002"), mk_item("70003")]
JUDG = {"70001": [mk_j(10)], "70002": [mk_j(150)], "70003": [{"error": "x"}]}   # 자동 · 멈춤 · 실패


@pytest.fixture
def client(tmp_path):
    (tmp_path / "weeks").mkdir()
    (tmp_path / "weeks" / f"{W}.json").write_text(json.dumps({"week": W, "items": ITEMS}), encoding="utf-8")
    (tmp_path / "runs" / W).mkdir(parents=True)
    (tmp_path / "runs" / W / "judgments.json").write_text(json.dumps(
        {"week": W, "model": "m", "samples": 1, "items": JUDG}), encoding="utf-8")
    (tmp_path / "runs" / "selected.json").write_text(json.dumps(
        {"name": "C1(£200)+C2+C4", "combo": ["C1:200", "C2", "C4"], "fallback": False}), encoding="utf-8")
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "index.html").write_text("<!doctype html><title>t</title>", encoding="utf-8")
    app = create_app(f"sqlite:///{tmp_path}/app.sqlite", f"sqlite:///{tmp_path}/cp.sqlite",
                     runs_dir=tmp_path / "runs", weeks_dir=tmp_path / "weeks",
                     web_dir=tmp_path / "web", sync_runs=True)
    c = TestClient(app)
    c.app_ref = app
    return c


def session(c):
    return c.post("/api/session").json()["session"]


def h(s, key=None):
    return {"X-Session": s, **({"X-OpenAI-Key": key} if key else {})}


def test_full_flow_auto_pending_and_approve(client):
    s = session(client)
    assert client.post("/api/run", json={"week": W}, headers=h(s)).status_code == 202
    sm = client.get(f"/api/summary?week={W}", headers=h(s)).json()
    assert sm["total"] == 3 and sm["counts"]["auto_sent"] == 1 and sm["pending"] == 2
    pend = client.get(f"/api/pending?week={W}", headers=h(s)).json()["items"]
    assert {p["code"] for p in pend} == {"70002", "70003"}
    tid = next(p["thread_id"] for p in pend if p["code"] == "70002")
    o = client.get(f"/api/orders/{tid}", headers=h(s)).json()
    for k in ("name_en", "qty", "amount_krw", "hist8", "reason_ko", "flags", "if_approved"):
        assert k in o
    assert "actual" not in json.dumps(o)            # 정답은 결재 화면에 없다
    r = client.post(f"/api/orders/{tid}/decision", json={"action": "approve"}, headers=h(s))
    assert r.json() == {"status": "approved"}
    fax = client.get("/api/faxlog", headers=h(s)).json()["items"]
    assert sorted(f["po"]["by"] for f in fax) == ["auto", "human"]


def test_second_decision_409(client):
    s = session(client)
    client.post("/api/run", json={"week": W}, headers=h(s))
    tid = f"{s}:{W}:70002"
    assert client.post(f"/api/orders/{tid}/decision", json={"action": "approve"}, headers=h(s)).status_code == 200
    assert client.post(f"/api/orders/{tid}/decision", json={"action": "approve"}, headers=h(s)).status_code == 409


def test_bad_edit_400(client):
    s = session(client)
    client.post("/api/run", json={"week": W}, headers=h(s))
    tid = f"{s}:{W}:70002"
    for q in ("abc", -1, 10.5, 10**9):
        r = client.post(f"/api/orders/{tid}/decision", json={"action": "edit", "qty": q}, headers=h(s))
        assert r.status_code == 400 and r.json()["detail"]
    assert client.get(f"/api/orders/{tid}", headers=h(s)).json()["pending"] is True


def test_redo_without_key_400_and_failed_item_cannot_be_approved(client):
    s = session(client)
    client.post("/api/run", json={"week": W}, headers=h(s))
    r = client.post(f"/api/orders/{s}:{W}:70002/decision", json={"action": "redo", "instruction": "x"}, headers=h(s))
    assert r.status_code == 400
    r = client.post(f"/api/orders/{s}:{W}:70003/decision", json={"action": "approve"}, headers=h(s))
    assert r.status_code == 400


def test_session_guards(client):
    s1, s2 = session(client), session(client)
    client.post("/api/run", json={"week": W}, headers=h(s1))
    assert client.get(f"/api/pending?week={W}").status_code == 401
    assert client.get(f"/api/pending?week={W}", headers=h("nope")).status_code == 401
    r = client.post(f"/api/orders/{s1}:{W}:70002/decision", json={"action": "approve"}, headers=h(s2))
    assert r.status_code == 403


def test_run_twice_409_and_reset(client):
    s = session(client)
    client.post("/api/run", json={"week": W}, headers=h(s))
    assert client.post("/api/run", json={"week": W}, headers=h(s)).status_code == 409
    assert client.post("/api/reset", headers=h(s)).json() == {"ok": True}
    assert client.get(f"/api/summary?week={W}", headers=h(s)).json()["total"] == 0
    assert client.post("/api/run", json={"week": W}, headers=h(s)).status_code == 202


def test_unknown_week_404_and_live_without_key_400(client):
    s = session(client)
    assert client.post("/api/run", json={"week": "1999-01-04"}, headers=h(s)).status_code == 404
    assert client.post("/api/run", json={"week": W, "live": True}, headers=h(s)).status_code == 400


def test_stale_badge_after_72h(client):
    s = session(client)
    client.post("/api/run", json={"week": W}, headers=h(s))
    store = client.app_ref.state.store
    store._q("UPDATE orders SET created_at = ? WHERE session = ?", (time.time() - 73 * 3600, s))
    pend = client.get(f"/api/pending?week={W}", headers=h(s)).json()["items"]
    assert all(p["stale"] for p in pend)


def test_static_index_served(client):
    assert "<title>t</title>" in client.get("/").text
