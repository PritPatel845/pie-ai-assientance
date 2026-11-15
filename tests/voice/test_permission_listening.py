from __future__ import annotations

import asyncio

from pie.config import VoiceConfig
from pie.events import Event, EventBus
from pie.inputs.voice.pipeline import VoiceController


def test_permission_request_opens_temporary_bare_confirmation_window() -> None:
    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        bus = EventBus(loop)
        controller = VoiceController(
            object(),
            bus=bus,
            config=VoiceConfig(),
            clock=lambda: 10.0,
            wall_clock=lambda: 100.0,
        )
        event = Event(
            topic="permission.request",
            payload={"timeout_s": 20.0},
            source="permission_gate",
            ts=100.0,
            id="request",
        )

        controller._on_permission_request(event)

        assert controller._active_until == 30.0
        controller.stop()

    asyncio.run(scenario())


def test_permission_request_window_is_capped() -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        controller = VoiceController(
            object(),
            bus=bus,
            config=VoiceConfig(),
            clock=lambda: 10.0,
            wall_clock=lambda: 100.0,
        )
        event = Event(
            topic="permission.request",
            payload={"timeout_s": 9999.0},
            source="permission_gate",
            ts=100.0,
            id="request",
        )

        controller._on_permission_request(event)

        assert controller._active_until == 130.0
        controller.stop()

    asyncio.run(scenario())
