from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from pie.inputs.voice.commands import parse_voice_command


class LegacyRuleExecutor:
    """Phase 0S phrase-to-controller adapter. Parsing is separate from effects."""

    def __init__(self, controller: Any, no_actions: bool = False) -> None:
        self.controller = controller
        self.no_actions = no_actions

    def run(self, action: str, value: object | None) -> bool:
        if action == "stop":
            return False
        if self.no_actions:
            return True
        if action == "delete":
            return bool(self.controller.delete_selected())
        if action == "close":
            return bool(self.controller.close_frontmost())
        if action == "hide":
            return bool(self.controller.hide_frontmost())
        if action == "key":
            if not isinstance(value, tuple):
                return False
            return bool(self.controller.key_combo(*value))
        if action == "open":
            target = str(value)
            if "://" in target:
                return bool(self.controller.open_target(target))
            if target.startswith(("/", "~", ".")):
                from pathlib import Path

                return bool(self.controller.open_target(str(Path(target).expanduser())))
            return bool(self.controller.open_application_or_item(target))
        if action == "search":
            return bool(
                self.controller.open_target(
                    "https://www.google.com/search?q=" + quote_plus(str(value))
                )
            )
        if action == "type":
            return bool(self.controller.type_text(str(value)))
        if action == "play":
            return bool(self.controller.play_media())
        if action == "pause":
            return bool(self.controller.stop_media())
        if action == "mute":
            return bool(self.controller.mute())
        if action == "settings":
            return bool(self.controller.open_system_settings())
        if action == "volume":
            return bool(self.controller.set_volume(int(value)))
        if action == "scroll":
            return bool(self.controller.scroll(int(value)))
        if action == "screenshot":
            return bool(self.controller.screenshot())
        if action == "lock":
            return bool(self.controller.lock_screen())
        return False

    def execute(self, text: str) -> bool:
        parsed = parse_voice_command(text)
        if parsed is None:
            return False
        return self.run(*parsed)


class VoiceController:
    def __init__(
        self,
        controller: Any,
        *,
        no_actions: bool = False,
        listen_seconds: int = 20,
        learning_engine: Any | None = None,
    ) -> None:
        if listen_seconds < 5:
            raise ValueError("listen_seconds must be at least 5")
        self.learning_engine = learning_engine
        self.executor = LegacyRuleExecutor(controller, no_actions)
        self.listen_seconds = listen_seconds

    def execute(self, command: str) -> bool:
        if self.learning_engine is not None:
            self.learning_engine.record_voice_command(command)
        return self.executor.execute(command)

    def start(self) -> None:
        # Phase 2A replaces this safe stub with offline microphone capture.
        return None
