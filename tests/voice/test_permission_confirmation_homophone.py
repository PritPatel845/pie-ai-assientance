from __future__ import annotations

import asyncio

import numpy as np

from pie.config import VoiceConfig
from pie.events import EventBus
from pie.inputs.voice.pipeline import VoiceController
from pie.inputs.voice.vad import Segment


class _Transcriber:
    name = "test"

    def __init__(self, text: str) -> None:
        self.text = text

    def transcribe(self, audio, language):
        return self.text

    def close(self) -> None:
        return None


def _run_transcript(text: str) -> dict:
    async def scenario() -> dict:
        bus = EventBus(asyncio.get_running_loop())
        controller = VoiceController(
            object(), bus=bus, config=VoiceConfig(), clock=lambda: 10.0, wall_clock=lambda: 100.0
        )
        controller._active_until = 30.0
        controller._transcriber = _Transcriber(text)
        events = []
        unsubscribe = bus.subscribe("input.voice.transcript", events.append, name="test-transcript")
        controller._handle_segment(Segment(np.ones(16_000, dtype=np.float32), 0.0, 1.0))
        await asyncio.sleep(0.05)
        unsubscribe()
        controller.stop()
        assert events
        return dict(events[0].payload)

    return asyncio.run(scenario())


def test_permission_window_accepts_exact_pie_homophone_confirmation() -> None:
    payload = _run_transcript("Bye. Yes.")
    assert payload["text"] == "yes"
    assert payload["addressed"] is True


def test_permission_window_accepts_exact_no_with_wake_prefix() -> None:
    payload = _run_transcript("Pie, no.")
    assert payload["text"] == "no"
    assert payload["addressed"] is True


def test_permission_window_does_not_extract_yes_from_arbitrary_sentence() -> None:
    payload = _run_transcript("I said bye yesterday, yes maybe.")
    assert payload["text"] == "I said bye yesterday, yes maybe."
    assert payload["addressed"] is True
