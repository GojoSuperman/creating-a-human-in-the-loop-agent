import asyncio

from server.events import EventBus


def test_publish_from_thread_reaches_subscriber():
    async def main():
        bus = EventBus()
        q = bus.subscribe("S")
        await asyncio.to_thread(bus.publish, "S", {"type": "sent"})
        bus.publish("OTHER", {"type": "x"})
        e = await asyncio.wait_for(q.get(), 1)
        bus.unsubscribe("S", q)
        return e, q.empty()
    e, empty = asyncio.run(main())
    assert e == {"type": "sent"} and empty
