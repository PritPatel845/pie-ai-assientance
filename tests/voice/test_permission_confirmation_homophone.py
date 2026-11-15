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


def test_permission_window_accepts_exact_wake_prefixed_confirmation_with_pie_homophone() -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        controller = VoiceController(
            object(), bus=bus, config=VoiceConfig(), clock=lambda: 10.0, wall_clock=lambda: 100.0
        )
        controller._active_until = 30.0

        import numpy as np
        from pie.inputs.voice.vad import Segment

        class Transcriber:
            name = "test"
            def transcribe(self, audio, language):
                return "Bye. Yes."
            def close(self):
                return None

        controller._transcriber = Transcriber()
        events = []
        unsubscribe = bus.subscribe("input.voice.transcript", events.append, name="test-transcript")
        controller._handle_segment(Segment(np.ones(16_000, dtype=np.float32), 0.0, 1.0))
        await asyncio.sleep(0.05)
        assert events
        assert events[0].payload["text"] == "yes"
        assert events[0].payload["addressed"] is True
        unsubscribe()
        controller.stop()

    asyncio.run(scenario())


def test_permission_window_does_not_extract_yes_from_arbitrary_sentence() -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        controller = VoiceController(
            object(), bus=bus, config=VoiceConfig(), clock=lambda: 10.0, wall_clock=lambda: 100.0
        )
        controller._active_until = 30.0

        import numpy as np
        from pie.inputs.voice.vad import Segment

        class Transcriber:
            name = "test"
            def transcribe(self, audio, language):
                return "I said bye yesterday, yes maybe."
            def close(self):
                return None

        controller._transcriber = Transcriber()
        events = []
        unsubscribe = bus.subscribe("input.voice.transcript", events.append, name="test-transcript")
        controller._handle_segment(Segment(np.ones(16_000, dtype=np.float32), 0.0, 1.0))
        await asyncio.sleep(0.05)
        assert events
        assert events[0].payload["text"] == "I said bye yesterday, yes maybe."
        unsubscribe()
        controller.stop()

    asyncio.run(scenario())
