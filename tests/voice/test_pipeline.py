from __future__ import annotations

import asyncio
import threading
from typing import Any

import numpy as np

from pie.config import VoiceConfig
from pie.events import Event, EventBus
from pie.inputs.voice.pipeline import VoiceController


class FakeTranscriber:
    name = "fake"

    def transcribe(self, audio: np.ndarray, language: str) -> str:
        assert audio.dtype == np.float32
        return "hey pie open safari"

    def close(self) -> None:
        return None


class FakeInputStream:
    def __init__(self, **kwargs: Any) -> None:
        self.callback = kwargs["callback"]

    def __enter__(self) -> FakeInputStream:
        rate = 16_000
        for index in range(32):
            samples = np.arange(512, dtype=np.float32) + index * 512
            tone = (0.08 * np.sin(2 * np.pi * 440 * samples / rate)).astype(np.float32)
            self.callback(tone.reshape(-1, 1), 512, None, None)
        silence = np.zeros((512, 1), dtype=np.float32)
        for _ in range(22):
            self.callback(silence, 512, None, None)
        return self

    def __exit__(self, *args: object) -> None:
        return None


class FakeMacController:
    def __init__(self) -> None:
        self.opened: list[str] = []
        self.called = threading.Event()

    def open_application_or_item(self, target: str) -> bool:
        self.opened.append(target)
        self.called.set()
        return True


def test_fake_microphone_pipeline_publishes_and_executes_in_order() -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        events: list[Event] = []
        transcript_ready = asyncio.Event()

        async def collect(event: Event) -> None:
            events.append(event)
            if event.topic == "input.voice.transcript":
                transcript_ready.set()

        bus.subscribe("input.voice.*", collect, name="pipeline-test")
        mac = FakeMacController()
        controller = VoiceController(
            mac,
            bus=bus,
            config=VoiceConfig(
                enabled=True,
                listen_seconds=5,
                vad_threshold=0.015,
                vad_min_speech_ms=150,
                vad_end_silence_ms=600,
                tts_enabled=False,
            ),
            stream_factory=FakeInputStream,
            transcriber_factory=lambda *args, **kwargs: FakeTranscriber(),
        )
        controller.start()
        try:
            await asyncio.wait_for(transcript_ready.wait(), timeout=2)
            assert await asyncio.to_thread(mac.called.wait, 1)
            topics = [event.topic for event in events]
            assert topics == [
                "input.voice.wake",
                "input.voice.listening",
                "input.voice.transcript",
            ]
            transcript = events[-1].payload
            assert transcript["text"] == "open safari"
            assert transcript["raw"] == "hey pie open safari"
            assert transcript["addressed"] is True
            assert mac.opened == ["safari"]
        finally:
            controller.stop()

    asyncio.run(scenario())
