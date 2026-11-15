from __future__ import annotations

from pie.events import EventBus


class TextInput:
    """Small adapter that publishes typed user commands without executing them."""

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus

    def submit(self, text: str) -> None:
        value = text.strip()
        if value:
            self.bus.publish("input.text.command", {"text": value}, source="text")
