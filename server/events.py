"""그래프가 도는 스레드 → SSE 구독자(이벤트 루프)로 이벤트를 넘긴다."""
import asyncio
import threading
from collections import defaultdict


class EventBus:
    def __init__(self):
        self.subs = defaultdict(list)
        self.lock = threading.Lock()
        self.loop = None

    def subscribe(self, session):
        self.loop = asyncio.get_running_loop()
        q = asyncio.Queue()
        with self.lock:
            self.subs[session].append(q)
        return q

    def unsubscribe(self, session, q):
        with self.lock:
            if q in self.subs.get(session, []):
                self.subs[session].remove(q)

    def publish(self, session, event):
        with self.lock:
            qs = list(self.subs.get(session, []))
        if qs and self.loop and not self.loop.is_closed():
            for q in qs:
                self.loop.call_soon_threadsafe(q.put_nowait, event)
