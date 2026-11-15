from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from pie.events import EventBus
from pie.inputs.gesture.bindings import GestureBindingsModule
from pie.inputs.gesture.frame import Mute, PlayMedia, RunVoiceCommand, StopMedia
from pie.inputs.gesture.runner import ActionSink


class FakeRegistry:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any], str]] = []

    async def execute(
        self,
        name: str,
        args: dict[str, Any],
        *,
        source: str,
        correlation_id: str | None = None,
    ) -> SimpleNamespace:
        del correlation_id
        self.calls.append((name, args, source))
        return SimpleNamespace(ok=True)


def test_discrete_gesture_tools_only_run_when_armed() -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        registry = FakeRegistry()
        daemon = SimpleNamespace(
            bus=bus,
            tool_registry=registry,
            config=SimpleNamespace(
                gesture=SimpleNamespace(
                    bindings_via_tools=True,
                    bindings={"thumb_up": "media.play"},
                )
            ),
        )
        module = GestureBindingsModule()
        module.start(daemon)
        await asyncio.sleep(0)
        bus.publish(
            "input.gesture.event",
            {"name": "thumb_up", "hand": "right", "confidence": 1.0},
            source="gesture",
        )
        await asyncio.sleep(0.01)
        assert registry.calls == []
        bus.publish("input.gesture.state", {"armed": True}, source="gesture")
        bus.publish(
            "input.gesture.event",
            {"name": "thumb_up", "hand": "right", "confidence": 1.0},
            source="gesture",
        )
        await asyncio.sleep(0.01)
        assert registry.calls == [("media.play", {}, "gesture")]
        module.stop()

    asyncio.run(scenario())


def test_gesture_binding_debounces_repeated_events() -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        registry = FakeRegistry()
        daemon = SimpleNamespace(
            bus=bus,
            tool_registry=registry,
            config=SimpleNamespace(
                gesture=SimpleNamespace(
                    bindings_via_tools=True,
                    bindings={"thumb_down": "media.pause"},
                )
            ),
        )
        module = GestureBindingsModule()
        module.start(daemon)
        await asyncio.sleep(0)
        bus.publish("input.gesture.state", {"armed": True}, source="gesture")
        for _ in range(2):
            bus.publish(
                "input.gesture.event",
                {"name": "thumb_down", "hand": "right", "confidence": 1.0},
                source="gesture",
            )
            await asyncio.sleep(0.01)
        assert len(registry.calls) == 1
        module.stop()

    asyncio.run(scenario())


class FakeController:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def mute(self) -> None:
        self.calls.append("mute")

    def play_media(self) -> None:
        self.calls.append("play")

    def stop_media(self) -> None:
        self.calls.append("pause")

    def run_voice_command(self) -> None:
        self.calls.append("unsafe-voice-command")


def test_discrete_media_gestures_do_not_bypass_registry() -> None:
    controller = FakeController()
    sink = ActionSink(controller, bindings_via_tools=True)
    sink.execute(Mute())
    sink.execute(PlayMedia())
    sink.execute(StopMedia())
    sink.execute(RunVoiceCommand())
    assert controller.calls == []


def test_legacy_direct_media_actions_require_explicit_opt_out() -> None:
    controller = FakeController()
    sink = ActionSink(controller, bindings_via_tools=False)
    sink.execute(Mute())
    sink.execute(PlayMedia())
    sink.execute(StopMedia())
    sink.execute(RunVoiceCommand())
    assert controller.calls == ["mute", "play", "pause"]
