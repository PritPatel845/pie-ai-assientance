import asyncio
import threading

from pie.core.events import EventBus


def test_event_bus_delivers_to_matching_subscriber() -> None:
    async def run() -> None:
        bus = EventBus(asyncio.get_running_loop())
        received = asyncio.Event()
        values: list[dict[str, int]] = []

        async def handler(event) -> None:
            values.append(event.payload)
            received.set()

        bus.subscribe("input.*", handler)
        bus.publish("input.voice", {"n": 1})
        await asyncio.wait_for(received.wait(), 1)
        assert values == [{"n": 1}]
        await bus.close()
    asyncio.run(run())


def test_publish_is_safe_from_worker_thread() -> None:
    async def run() -> None:
        bus = EventBus(asyncio.get_running_loop())
        received = asyncio.Event()
        seen: list[str] = []

        async def handler(event) -> None:
            seen.append(event.topic)
            received.set()

        bus.subscribe("system.*", handler)
        worker = threading.Thread(target=bus.publish, args=("system.ready", {}))
        worker.start()
        worker.join()
        await asyncio.wait_for(received.wait(), 1)
        assert seen == ["system.ready"]
        await bus.close()
    asyncio.run(run())


def test_subscriber_failure_does_not_kill_bus() -> None:
    async def run() -> None:
        bus = EventBus(asyncio.get_running_loop())
        received = asyncio.Event()

        async def broken(event) -> None:
            raise ValueError("expected")

        async def healthy(event) -> None:
            if event.topic == "input.test":
                received.set()

        bus.subscribe("input.*", broken)
        bus.subscribe("input.*", healthy)
        bus.publish("input.test", {})
        await asyncio.wait_for(received.wait(), 1)
        await bus.close()
    asyncio.run(run())
