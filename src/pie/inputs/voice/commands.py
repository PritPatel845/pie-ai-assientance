from __future__ import annotations

import re

VOICE_WAKE_WORDS = ("hey pie", "pie", "pi", "jr", "j r", "jay r", "jarvis")


def extract_wake_command(text: str) -> str | None:
    cleaned = re.sub(r"\s+", " ", text.strip().lower())
    for wake in sorted(VOICE_WAKE_WORDS, key=len, reverse=True):
        match = re.match(rf"^(?:hey\s+)?{re.escape(wake)}(?=$|[\s,.!?])", cleaned)
        if match:
            return cleaned[match.end() :].lstrip(" ,.!?")
    return None


def parse_voice_command(text: str) -> tuple[str, object | None] | None:
    value = re.sub(r"\s+", " ", text.strip().lower())
    exact: dict[str, tuple[str, object | None]] = {
        "stop listening": ("stop", None),
        "pause listening": ("stop", None),
        "voice off": ("stop", None),
        "confirm delete": ("delete", None),
        "yes delete": ("delete", None),
        "delete it": ("delete", None),
        "close window": ("close", None),
        "close app": ("close", None),
        "close application": ("close", None),
        "quit app": ("close", None),
        "hide window": ("hide", None),
        "hide app": ("hide", None),
        "undo": ("key", ("command", "z")),
        "undo that": ("key", ("command", "z")),
        "redo": ("key", ("command", "shift", "z")),
        "redo that": ("key", ("command", "shift", "z")),
        "copy": ("key", ("command", "c")),
        "copy that": ("key", ("command", "c")),
        "paste": ("key", ("command", "v")),
        "paste that": ("key", ("command", "v")),
        "select all": ("key", ("command", "a")),
        "select everything": ("key", ("command", "a")),
        "play": ("play", None),
        "play music": ("play", None),
        "resume music": ("play", None),
        "pause": ("pause", None),
        "pause music": ("pause", None),
        "stop music": ("pause", None),
        "mute": ("mute", None),
        "mute audio": ("mute", None),
        "silence": ("mute", None),
        "settings": ("settings", None),
        "system settings": ("settings", None),
        "system preferences": ("settings", None),
        "open settings": ("settings", None),
        "screenshot": ("screenshot", None),
        "take a screenshot": ("screenshot", None),
        "capture screen": ("screenshot", None),
        "lock screen": ("lock", None),
        "lock the screen": ("lock", None),
        "scroll up": ("scroll", 5),
        "page up": ("scroll", 5),
        "scroll down": ("scroll", -5),
        "page down": ("scroll", -5),
    }
    if value in exact:
        return exact[value]
    match = re.fullmatch(r"(?:volume|set volume|set the volume to|volume to)\s+(\d{1,3})", value)
    if match:
        return "volume", min(100, int(match.group(1)))
    match = re.fullmatch(r"(?:search|ask|look up)\s+(.+)", value)
    if match:
        query = re.sub(r"^(?:the web for|google)\s+", "", match.group(1))
        return "search", query
    for prefix in ("open", "launch", "start", "type", "write", "enter"):
        if value.startswith(prefix + " "):
            action = "open" if prefix in ("open", "launch", "start") else "type"
            return action, value[len(prefix) + 1 :]
    return None
