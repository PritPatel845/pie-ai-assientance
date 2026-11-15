from __future__ import annotations

import importlib
import os
import shlex
import subprocess
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

Runner = Callable[..., subprocess.CompletedProcess[str]]

SYSTEM_APP_ALIASES = {
    "settings": "System Settings",
    "system settings": "System Settings",
    "system preferences": "System Settings",
    "preferences": "System Settings",
    "terminal": "Terminal",
    "finder": "Finder",
    "launchpad": "Launchpad",
    "calendar": "Calendar",
    "notes": "Notes",
    "mail": "Mail",
    "music": "Music",
    "spotify": "Spotify",
    "safari": "Safari",
    "chrome": "Google Chrome",
    "firefox": "Firefox",
    "messages": "Messages",
    "facetime": "FaceTime",
    "camera": "Photo Booth",
    "photos": "Photos",
    "reminders": "Reminders",
    "maps": "Maps",
    "contacts": "Contacts",
    "clock": "Clock",
    "calculator": "Calculator",
    "weather": "Weather",
    "whatsapp": "WhatsApp",
    "steam": "Steam",
    "vs code": "Visual Studio Code",
    "claude": "Claude",
    "asphalt": "Asphalt 8: Airborne",
    "asplasht": "Asphalt 8: Airborne",
}
FOLDER_ALIASES = {"downloads": "Downloads", "documents": "Documents", "desktop": "Desktop"}


def resolve_system_application(name: str) -> str | None:
    spoken = name.strip().lower()
    if spoken in SYSTEM_APP_ALIASES:
        return SYSTEM_APP_ALIASES[spoken]
    matches = [
        (alias, app)
        for alias, app in SYSTEM_APP_ALIASES.items()
        if alias in spoken or spoken in alias
    ]
    return max(matches, key=lambda pair: len(pair[0]))[1] if matches else None


class MacController:
    def __init__(
        self,
        runner: Runner = subprocess.run,
        *,
        poster: Any | None = None,
        screen_size: Callable[[], tuple[int, int]] | None = None,
        media_key: Callable[[], None] | None = None,
    ) -> None:
        self._runner, self._poster, self._screen_size = runner, poster, screen_size
        self._media_key = media_key

    def _run(self, argv: Sequence[str], timeout: float = 5.0) -> bool:
        if not argv or argv[0] not in {
            "/usr/bin/open",
            "/usr/bin/osascript",
            "/usr/sbin/screencapture",
        }:
            raise ValueError("Executable is not allow-listed")
        try:
            result = self._runner(
                list(argv),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0

    def open_target(self, target: str) -> bool:
        return self._run(("/usr/bin/open", target))

    def open_application(self, name: str) -> bool:
        return bool(name.strip()) and self._run(("/usr/bin/open", "-a", name.strip()))

    def open_application_or_item(self, target: str) -> bool:
        cleaned = target.strip()
        if not cleaned:
            return False
        if cleaned.lower() in FOLDER_ALIASES:
            return self.open_target(str(Path.home() / FOLDER_ALIASES[cleaned.lower()]))
        app = resolve_system_application(cleaned)
        if app:
            return self.open_application(app)
        query = cleaned.replace('"', r"\"")
        roots = (
            "/Applications",
            str(Path.home() / "Applications"),
            "/System/Applications",
            "/System/Applications/Utilities",
        )
        try:
            result = self._runner(
                [
                    "/usr/bin/mdfind",
                    "-onlyin",
                    roots[0],
                    "-onlyin",
                    roots[1],
                    "-onlyin",
                    roots[2],
                    "-onlyin",
                    roots[3],
                    f'kMDItemKind == "Application" && kMDItemDisplayName == "*{query}*"',
                ],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return self.open_application(cleaned)
        matches = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
        return self.open_target(matches[0]) if matches else self.open_application(cleaned)

    def _osascript(self, script: str) -> bool:
        return self._run(("/usr/bin/osascript", "-e", script))

    def mute(self) -> bool:
        return self._osascript("set volume output muted true")

    def set_volume(self, value: int) -> bool:
        return self._osascript(f"set volume output volume {max(0, min(100, int(value)))}")

    def _press_media_key(self) -> bool:
        try:
            if self._media_key is not None:
                self._media_key()
            else:
                pyautogui = importlib.import_module("pyautogui")
                if "playpause" not in pyautogui.KEYBOARD_KEYS:
                    return False
                pyautogui.press("playpause")
        except (ImportError, OSError, RuntimeError):
            return False
        return True

    def _control_media(self, command: str) -> bool:
        try:
            result = self._runner(
                [
                    "/usr/bin/osascript",
                    "-e",
                    (
                        'tell application "System Events" to get name of every process '
                        "whose background only is false"
                    ),
                ],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return self._press_media_key()
        if result.returncode == 0:
            running = set((result.stdout or "").split(", "))
            for app in ("Spotify", "Music"):
                if app in running:
                    if self._osascript(f'tell application "{app}" to {command}'):
                        return True
                    break
        return self._press_media_key()

    def play_media(self) -> bool:
        return self._control_media("play")

    def stop_media(self) -> bool:
        return self._control_media("pause")

    def show_voice_activation(self, listen_seconds: int) -> bool:
        seconds = max(5, int(listen_seconds))
        message = f"Listening for your command for {seconds} seconds."
        script = f'display notification "{message}" with title "PIE ACTIVE"'
        return self._osascript(script)

    def open_system_settings(self) -> bool:
        return self.open_application("System Settings")

    def move_cursor(self, x: float, y: float) -> bool:
        pyautogui = importlib.import_module("pyautogui")

        width, height = self._screen_size() if self._screen_size else pyautogui.size()
        pyautogui.moveTo(
            int(max(0, min(1, x)) * (width - 1)), int(max(0, min(1, y)) * (height - 1))
        )
        return True

    def click(self) -> bool:
        pyautogui = importlib.import_module("pyautogui")

        pyautogui.click()
        return True

    def double_click(self) -> bool:
        pyautogui = importlib.import_module("pyautogui")

        pyautogui.doubleClick(interval=0.08)
        return True

    def scroll(self, amount: int) -> bool:
        pyautogui = importlib.import_module("pyautogui")

        pyautogui.scroll(int(amount))
        return True

    def key_combo(self, *keys: str) -> bool:
        pyautogui = importlib.import_module("pyautogui")

        pyautogui.hotkey(*keys)
        return True

    def type_text(self, text: str) -> bool:
        pyautogui = importlib.import_module("pyautogui")

        pyautogui.write(text, interval=0.01)
        return True

    def screenshot(self) -> bool:
        filename = (
            Path.home() / "Desktop" / f"Pie Screenshot {datetime.now():%Y-%m-%d %H-%M-%S}.png"
        )
        return self._run(("/usr/sbin/screencapture", "-x", str(filename)))

    def lock_screen(self) -> bool:
        return self.key_combo("command", "control", "q")

    def hide_frontmost(self) -> bool:
        return self.key_combo("command", "h")

    def close_frontmost(self) -> bool:
        return self.key_combo("command", "q")

    def delete_selected(self) -> bool:
        return self.key_combo("command", "backspace")

    def run_voice_command(self) -> bool:
        command = os.environ.get("PIE_VOICE_COMMAND", "").strip()
        if not command:
            return False
        try:
            argv = shlex.split(command)
        except ValueError:
            return False
        return (
            self._run(argv)
            if argv and argv[0] in {"/usr/bin/open", "/usr/bin/osascript"}
            else False
        )

    def key_event(self, code: int, pressed: bool) -> None:
        if self._poster is not None:
            self._poster.key_event(code, pressed)
            return
        try:
            Quartz = importlib.import_module("Quartz")
        except ImportError as exc:
            raise RuntimeError("Quartz is required for game keyboard control") from exc
        event = Quartz.CGEventCreateKeyboardEvent(None, code, pressed)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def mouse_click(self) -> bool:
        Quartz = importlib.import_module("Quartz")

        point = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
        for event_type in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
            event = Quartz.CGEventCreateMouseEvent(
                None, event_type, point, Quartz.kCGMouseButtonLeft
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
        return True
