from __future__ import annotations

import asyncio
import time

import numpy as np

from pie.config import VoiceConfig
from pie.events import EventBus
from pie.inputs.voice.pipeline import VoiceController
from pie.inputs.voice.vad import Segment
from pie.safety.permissions import PermissionDecision, PermissionGate, Tier


class _Transcript:
    name = "test"

    def __init__(self, text: str) -> None:
        self.text = text

    def transcribe(self, audio, language):
        return self.text

    def close(self) -> None:
        return None


async def _run_voice_confirmation(transcript: str) -> PermissionDecision:
    loop = asyncio.get_running_loop()
    bus = EventBus(loop)
    gate = PermissionGate(bus, timeout_s=1.0)
    gate.start()
    voice = VoiceController(
        object(),
        bus=bus,
        config=VoiceConfig(),
        transcriber_factory=lambda *_args, **_kwargs: _Transcript(transcript),
    )
    try:
        request = asyncio.create_task(
            gate.request(
                call_id="voice-integration",
                tool="fs.write_text",
                args={"path": "~/PieWorkspace/test.txt", "content": "safe test"},
                tier=Tier.CONFIRM,
                prompt="Allow write?",
                timeout_s=1.0,
            )
        )
        deadline = time.monotonic() + 0.5
        while voice._active_until <= time.monotonic() and time.monotonic() < deadline:
            await asyncio.sleep(0.005)
        assert voice._active_until > time.monotonic(), "permission window did not open"
        voice._handle_segment(Segment(np.ones(16_000, dtype=np.float32), 0.0, 1.0))
        return await request
    finally:
        voice.stop()
        gate.stop()


def test_voice_transcript_resolves_pending_permission_end_to_end() -> None:
    async def scenario() -> None:
        decision = await _run_voice_confirmation("Bye. Yes.")
        assert decision == PermissionDecision(True, "voice")

    asyncio.run(scenario())


def test_voice_no_denies_pending_permission_end_to_end() -> None:
    async def scenario() -> None:
        decision = await _run_voice_confirmation("No.")
        assert decision == PermissionDecision(False, "voice")

    asyncio.run(scenario())


def test_unrelated_voice_sentence_does_not_resolve_pending_permission() -> None:
    async def scenario() -> None:
        decision = await _run_voice_confirmation("I said yes yesterday.")
        assert decision == PermissionDecision(False, "timeout")

    asyncio.run(scenario())
