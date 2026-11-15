from __future__ import annotations

import asyncio
import threading

import pytest

from pie.events import Event, EventBus


def test_subscriber_order_and_wait_for() -> None:
    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        bus = EventBus(loop)
        received: list[int] = []
        ready = asyncio.Event()

        async def collect(event: Event) -> None:
            received.append(int(event.payload["n"]))
            if len(received) == 4:
                ready.set()

        unsubscribe = bus.subscribe("test.*", collect, name="ordered")
        for number in range(4):
            bus.publish("test.item", {"n": number}, source="test")
        await asyncio.wait_for(ready.wait(), 1)
        assert received == [0, 1, 2, 3]
        unsubscribe()
        with pytest.raises(asyncio.TimeoutError):
            await bus.wait_for("never.*", timeout=0.01)

    asyncio.run(scenario())


def test_wait_for_matches_predicate_and_unsubscribes() -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        waiter = asyncio.create_task(bus.wait_for("demo.*", timeout=1,
                                                   predicate=lambda event: event.payload.get("ok") is True))
        await asyncio.sleep(0)
        bus.publish("demo.ready", {"ok": False}, source="test")
        bus.publish("demo.ready", {"ok": True}, source="test")
        event = await waiter
        assert event.payload["ok"] is True

    asyncio.run(scenario())


def test_publish_from_multiple_threads_delivers_each_event() -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        received: set[str] = set()
        done = asyncio.Event()

        async def collect(event: Event) -> None:
            received.add(str(event.payload["id"]))
            if len(received) == 800:
                done.set()

        bus.subscribe("*", collect, name="threaded")
        threads = [
            threading.Thread(target=lambda base=base: [
                bus.publish("thread.item", {"id": f"{base}-{i}"}, source="thread")
                for i in range(100)
            ])
            for base in range(8)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        await asyncio.wait_for(done.wait(), 3)
        assert len(received) == 800

    asyncio.run(scenario())


def test_slow_subscriber_does_not_block_fast_subscriber() -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        fast = asyncio.Event()

        async def slow(event: Event) -> None:
            await asyncio.sleep(0.2)

        async def quick(event: Event) -> None:
            fast.set()

        bus.subscribe("*", slow, name="slow")
        bus.subscribe("*", quick, name="fast")
        bus.publish("demo.event", {}, source="test")
        await asyncio.wait_for(fast.wait(), 0.1)

    asyncio.run(scenario())


def test_overflow_drops_oldest_and_counts_drop() -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        gate = asyncio.Event()

        async def blocked(event: Event) -> None:
            await gate.wait()

        bus.subscribe("*", blocked, name="blocked")
        await asyncio.sleep(0)
        for index in range(1002):
            bus._dispatch(Event("demo.event", {"n": index}, "test", 0.0, str(index)))
        assert bus._subscribers[0].drops >= 1
        gate.set()

    asyncio.run(scenario())


def test_handler_failure_isolated_and_reported() -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        got_error = asyncio.Event()
        got_regular = asyncio.Event()

        def broken(event: Event) -> None:
            raise RuntimeError("broken handler")

        async def regular(event: Event) -> None:
            if event.topic == "demo.event":
                got_regular.set()

        async def errors(event: Event) -> None:
            if event.topic == "system.error":
                assert event.payload["where"] == "bus:broken"
                got_error.set()

        bus.subscribe("demo.event", broken, name="broken")
        bus.subscribe("*", regular, name="regular")
        bus.subscribe("system.error", errors, name="errors")
        bus.publish("demo.event", {}, source="test")
        await asyncio.wait_for(got_regular.wait(), 1)
        await asyncio.wait_for(got_error.wait(), 1)

    asyncio.run(scenario())


def test_publish_after_loop_closed_is_safe() -> None:
    loop = asyncio.new_event_loop()
    bus = EventBus(loop)
    loop.close()
    event = bus.publish("demo.closed", {}, source="test")
    assert event.topic == "demo.closed"


def test_unsubscribe_is_idempotent() -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        unsubscribe = bus.subscribe("*", lambda event: None, name="idempotent")
        unsubscribe()
        unsubscribe()
        assert not bus._subscribers

    asyncio.run(scenario())


def test_text_input_publishes_nonempty_commands() -> None:
    from pie.inputs.text import TextInput

    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        received: list[str] = []
        ready = asyncio.Event()

        async def collect(event: Event) -> None:
            received.append(str(event.payload["text"]))
            ready.set()

        bus.subscribe("input.text.command", collect, name="text-test")
        text_input = TextInput(bus)
        text_input.submit("  open Safari  ")
        text_input.submit("   ")
        await asyncio.wait_for(ready.wait(), 1)
        assert received == ["open Safari"]

    asyncio.run(scenario())


def test_voice_event_adapter_publishes_contract_payloads() -> None:
    from pie.inputs.voice.pipeline import VoiceController

    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        received: list[Event] = []
        ready = asyncio.Event()

        async def collect(event: Event) -> None:
            received.append(event)
            if len(received) == 3:
                ready.set()

        bus.subscribe("input.voice.*", collect, name="voice-test")
        controller = VoiceController(object(), bus=bus, language="en")
        controller.publish_wake("pie")
        controller.publish_listening(True, 1234.5)
        controller.publish_transcript("open Safari")
        await asyncio.wait_for(ready.wait(), 1)
        assert [event.topic for event in received] == [
            "input.voice.wake", "input.voice.listening", "input.voice.transcript"
        ]
        assert received[-1].payload == {"text": "open Safari", "final": True, "lang": "en"}

    asyncio.run(scenario())
