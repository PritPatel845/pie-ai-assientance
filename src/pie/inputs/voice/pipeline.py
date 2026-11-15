from __future__ import annotations

from typing import Any

from pie.events import EventBus
from pie.inputs.voice.executor import VoiceController as _VoiceController


class VoiceController(_VoiceController):
    """Phase 1 event-aware adapter; microphone capture remains a Phase 2A feature."""

    def __init__(
        self,
        controller: Any,
        *,
        no_actions: bool = False,
        listen_seconds: int = 20,
        learning_engine: Any | None = None,
        bus: EventBus | None = None,
        language: str = "en",
    ) -> None:
        super().__init__(
            controller,
            no_actions=no_actions,
            listen_seconds=listen_seconds,
            learning_engine=learning_engine,
        )
        self.bus = bus
        self.language = language

    def publish_wake(self, word: str) -> None:
        if self.bus is not None:
            self.bus.publish("input.voice.wake", {"word": word}, source="voice")

    def publish_listening(self, active: bool, until: float) -> None:
        if self.bus is not None:
            self.bus.publish(
                "input.voice.listening",
                {"active": active, "until": until},
                source="voice",
            )

    def publish_transcript(self, text: str, *, final: bool = True) -> None:
        if self.bus is not None:
            self.bus.publish(
                "input.voice.transcript",
                {"text": text, "final": final, "lang": self.language},
                source="voice",
            )

    def execute(self, command: str) -> bool:
        # Preserve the existing bounded parser and command executor unchanged.
        return super().execute(command)


__all__ = ["VoiceController"]
