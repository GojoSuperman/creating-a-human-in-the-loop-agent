"""주문 색인·팩스 로그·반려·세션. SQLite(로컬)와 Postgres(배포)를 같은 SQL로 쓴다."""
import json
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = [
    "CREATE TABLE IF NOT EXISTS sessions (session TEXT PRIMARY KEY, created_at DOUBLE PRECISION)",
    "CREATE TABLE IF NOT EXISTS orders (thread_id TEXT PRIMARY KEY, session TEXT, week TEXT, "
    "code TEXT, status TEXT, created_at DOUBLE PRECISION)",
    "CREATE TABLE IF NOT EXISTS fax (thread_id TEXT PRIMARY KEY, session TEXT, po TEXT, sent_at DOUBLE PRECISION)",
    "CREATE TABLE IF NOT EXISTS rejects (thread_id TEXT PRIMARY KEY, session TEXT, reason TEXT, at DOUBLE PRECISION)",
]


def _sqlite_path(url):
    p = Path(url.removeprefix("sqlite:///"))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


class Store:
    def __init__(self, url):
        self.pg = url.startswith("postgres")
        self.lock = threading.Lock()
        if self.pg:
            # 연결 하나를 붙잡지 않고 풀에서 빌린다 — Neon(서버리스) 은 유휴 연결을 닫기 때문에
            # (배포 실측: 닫힌 연결을 계속 써서 모든 요청이 500). 빌릴 때 살아 있는지 확인한다.
            self.pool = _pool(url, autocommit=True)
        else:
            self.conn = sqlite3.connect(_sqlite_path(url), check_same_thread=False, isolation_level=None)
        for sql in SCHEMA:
            self._q(sql)

    def _q(self, sql, args=(), fetch=False):
        if self.pg:
            with self.pool.connection() as conn:
                cur = conn.execute(sql.replace("?", "%s"), args)
                return _rows(cur) if fetch else cur.rowcount
        with self.lock:
            cur = self.conn.execute(sql, args)
            return _rows(cur) if fetch else cur.rowcount

    # 세션
    def create_session(self, sid, now=None):
        self._q("INSERT INTO sessions VALUES (?, ?) ON CONFLICT(session) DO NOTHING", (sid, now or time.time()))

    def session_exists(self, sid):
        return bool(self._q("SELECT 1 FROM sessions WHERE session = ?", (sid,), fetch=True))

    def old_sessions(self, hours, now=None):
        cut = (now or time.time()) - hours * 3600
        rows = self._q("SELECT session FROM sessions WHERE created_at < ? ORDER BY session", (cut,), fetch=True)
        return [r["session"] for r in rows]

    def delete_session(self, sid):
        tids = [r["thread_id"] for r in self._q("SELECT thread_id FROM orders WHERE session = ?", (sid,), fetch=True)]
        for t in ("orders", "fax", "rejects", "sessions"):
            self._q(f"DELETE FROM {t} WHERE session = ?", (sid,))
        return tids

    # 주문 색인
    def upsert_order(self, thread_id, session, week, code, status, now=None):
        n = self._q("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(thread_id) DO NOTHING",
                    (thread_id, session, week, code, status, now or time.time()))
        return n == 1

    def set_status(self, thread_id, status):
        self._q("UPDATE orders SET status = ? WHERE thread_id = ?", (status, thread_id))

    def orders(self, session, week=None):
        if week is None:
            return self._q("SELECT * FROM orders WHERE session = ? ORDER BY thread_id", (session,), fetch=True)
        return self._q("SELECT * FROM orders WHERE session = ? AND week = ? ORDER BY thread_id",
                       (session, week), fetch=True)

    # 팩스 — 바깥으로 나가는 유일한 기록. thread_id 로 멱등
    def fax_send(self, thread_id, session, po, now=None):
        n = self._q("INSERT INTO fax VALUES (?, ?, ?, ?) ON CONFLICT(thread_id) DO NOTHING",
                    (thread_id, session, json.dumps(po, ensure_ascii=False), now or time.time()))
        return n == 1

    def fax_list(self, session):
        rows = self._q("SELECT thread_id, po, sent_at FROM fax WHERE session = ? ORDER BY sent_at",
                       (session,), fetch=True)
        return [{**r, "po": json.loads(r["po"])} for r in rows]

    # 반려
    def add_reject(self, thread_id, session, reason, now=None):
        self._q("INSERT INTO rejects VALUES (?, ?, ?, ?) ON CONFLICT(thread_id) DO NOTHING",
                (thread_id, session, reason, now or time.time()))

    def rejects(self, session):
        return self._q("SELECT thread_id, reason, at FROM rejects WHERE session = ? ORDER BY at",
                       (session,), fetch=True)


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _pool(url, **kwargs):
    from psycopg_pool import ConnectionPool
    # check: 빌려줄 때마다 연결이 살아 있는지 확인하고 죽었으면 새로 연다
    # max_idle: Neon 이 닫기 전에 우리가 먼저 오래 쉰 연결을 버린다
    return ConnectionPool(url, min_size=1, max_size=5, kwargs=kwargs, check=ConnectionPool.check_connection,
                          max_idle=120, open=True)


def make_checkpointer(url):
    if url.startswith("postgres"):
        from psycopg.rows import dict_row
        from langgraph.checkpoint.postgres import PostgresSaver
        saver = PostgresSaver(_pool(url, autocommit=True, prepare_threshold=0, row_factory=dict_row))
        saver.setup()
        return saver
    from langgraph.checkpoint.sqlite import SqliteSaver
    return SqliteSaver(sqlite3.connect(_sqlite_path(url), check_same_thread=False))
