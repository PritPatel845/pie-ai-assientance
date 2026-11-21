from __future__ import annotations

import asyncio

from pie.events import EventBus
from pie.safety.permissions import PermissionDecision, PermissionGate, Tier


def _request(gate: PermissionGate, call_id: str = "call") -> asyncio.Task[PermissionDecision]:
    return asyncio.create_task(
        gate.request(
            call_id=call_id,
            tool="mac.type_text",
            args={"text": "hello"},
            tier=Tier.CONFIRM,
            prompt="Type the requested text?",
            timeout_s=0.05,
        )
    )


def test_addressed_voice_yes_approves_fifo_request() -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        gate = PermissionGate(bus, timeout_s=0.1)
        gate.start()
        await asyncio.sleep(0)
        task = _request(gate)
        await asyncio.sleep(0.01)
        bus.publish(
            "input.voice.transcript",
            {"final": True, "addressed": True, "text": "yes."},
            source="voice",
        )
        decision = await task
        assert decision.allow and decision.by == "voice"
        gate.stop()

    asyncio.run(scenario())


def test_unaddressed_voice_cannot_approve() -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        gate = PermissionGate(bus, timeout_s=0.02)
        gate.start()
        await asyncio.sleep(0)
        task = _request(gate)
        await asyncio.sleep(0.005)
        bus.publish(
            "input.voice.transcript",
            {"final": True, "addressed": False, "text": "yes"},
            source="voice",
        )
        decision = await task
        assert not decision.allow and decision.by == "timeout"
        gate.stop()

    asyncio.run(scenario())


def test_stale_yes_before_request_is_ignored() -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        gate = PermissionGate(bus, timeout_s=0.02)
        gate.start()
        await asyncio.sleep(0)
        bus.publish(
            "input.voice.transcript",
            {"final": True, "addressed": True, "text": "yes"},
            source="voice",
        )
        await asyncio.sleep(0.01)
        decision = await _request(gate)
        assert not decision.allow and decision.by == "timeout"
        gate.stop()

    asyncio.run(scenario())


def test_fifo_approval_resolves_oldest_request_first() -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        gate = PermissionGate(bus, timeout_s=0.2)
        gate.start()
        await asyncio.sleep(0)
        first = _request(gate, "first")
        await asyncio.sleep(0.005)
        second = _request(gate, "second")
        await asyncio.sleep(0.01)
        for _ in range(2):
            bus.publish(
                "input.voice.transcript",
                {"final": True, "addressed": True, "text": "yes"},
                source="voice",
            )
            await asyncio.sleep(0.005)
        first_decision, second_decision = await asyncio.gather(first, second)
        assert first_decision.allow and second_decision.allow
        gate.stop()

    asyncio.run(scenario())


def test_gesture_approval_requires_armed_state() -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        gate = PermissionGate(bus, timeout_s=0.1)
        gate.start()
        await asyncio.sleep(0)
        task = _request(gate)
        await asyncio.sleep(0.005)
        bus.publish("input.gesture.state", {"armed": False}, source="gesture")
        bus.publish(
            "input.gesture.event",
            {"name": "thumb_up", "hand": "right", "confidence": 1.0},
            source="gesture",
        )
        await asyncio.sleep(0.01)
        assert not task.done()
        bus.publish("input.gesture.state", {"armed": True}, source="gesture")
        bus.publish(
            "input.gesture.event",
            {"name": "thumb_up", "hand": "right", "confidence": 1.0},
            source="gesture",
        )
        decision = await task
        assert decision.allow and decision.by == "gesture"
        gate.stop()

    asyncio.run(scenario())


def test_gesture_thumb_down_denies_when_armed() -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        gate = PermissionGate(bus, timeout_s=0.1)
        gate.start()
        await asyncio.sleep(0)
        task = _request(gate)
        await asyncio.sleep(0.005)
        bus.publish("input.gesture.state", {"armed": True}, source="gesture")
        bus.publish(
            "input.gesture.event",
            {"name": "thumb_down", "hand": "right", "confidence": 1.0},
            source="gesture",
        )
        decision = await task
        assert not decision.allow and decision.by == "gesture"
        gate.stop()

    asyncio.run(scenario())


def test_ui_permission_event_resolves_oldest_request() -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        gate = PermissionGate(bus, timeout_s=0.1)
        gate.start()
        await asyncio.sleep(0)
        task = _request(gate)
        await asyncio.sleep(0.005)
        bus.publish("ui.command", {"name": "permission", "allow": True}, source="ui")
        decision = await task
        assert decision.allow and decision.by == "ui"
        gate.stop()

    asyncio.run(scenario())


def test_confirmation_spam_is_limited() -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        gate = PermissionGate(bus, timeout_s=0.2, max_prompts_per_min=1)
        gate.start()
        await asyncio.sleep(0)
        first = _request(gate, "first")
        await asyncio.sleep(0.005)
        second = _request(gate, "second")
        second_decision = await second
        assert not second_decision.allow
        assert second_decision.by == "too_many_confirmations"
        first.cancel()
        try:
            await first
        except asyncio.CancelledError:
            pass
        gate.stop()

    asyncio.run(scenario())


def test_permission_request_redacts_typed_and_written_content() -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        received = []
        bus.subscribe("permission.request", received.append, name="redaction-test")
        gate = PermissionGate(bus, timeout_s=0.1)
        gate.start()
        await asyncio.sleep(0)
        typed = asyncio.create_task(
            gate.request(
                call_id="typed",
                tool="mac.type_text",
                args={"text": "private text"},
                tier=Tier.CONFIRM,
                prompt="Type requested text?",
                timeout_s=0.1,
            )
        )
        await asyncio.sleep(0.01)
        assert received[-1].payload["args"]["text"] == {"length": 12}
        bus.publish(
            "input.voice.transcript",
            {"final": True, "addressed": True, "text": "yes"},
            source="voice",
        )
        assert (await typed).allow

        written = asyncio.create_task(
            gate.request(
                call_id="written",
                tool="fs.write_text",
                args={"path": "~/PieWorkspace/test.txt", "content": "private file"},
                tier=Tier.CONFIRM,
                prompt="Write requested file?",
                timeout_s=0.1,
            )
        )
        await asyncio.sleep(0.01)
        assert received[-1].payload["args"]["content"] == {"length": 12}
        bus.publish(
            "input.voice.transcript",
            {"final": True, "addressed": True, "text": "yes"},
            source="voice",
        )
        assert (await written).allow
        gate.stop()

    asyncio.run(scenario())


def test_default_permission_timeout_is_45_seconds() -> None:
    bus = EventBus(asyncio.new_event_loop())
    gate = PermissionGate(bus)
    assert gate.timeout_s == 45.0
    gate.stop()
    bus.loop.close()
