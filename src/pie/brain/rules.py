from __future__ import annotations

import uuid
from dataclasses import dataclass

from pie.brain.types import ToolCall
from pie.inputs.voice.commands import parse_voice_command


@dataclass(frozen=True, slots=True)
class RuleMatch:
    action: str
    value: object | None
    phrase: str = ""


def match_rule(text: str) -> RuleMatch | None:
    parsed = parse_voice_command(text)
    if parsed is None:
        return None
    return RuleMatch(parsed[0], parsed[1], " ".join(text.strip().casefold().split()))


_LOCAL_PHRASES = (
    "use the local model",
    "use local model",
    "use local",
    "locally",
    "offline",
    "without internet",
    "on device",
)


def wants_local(text: str) -> tuple[bool, str]:
    cleaned = " ".join(text.strip().split())
    lowered = cleaned.casefold()
    for phrase in _LOCAL_PHRASES:
        if lowered == phrase:
            return True, ""
        if lowered.startswith(phrase + " "):
            return True, cleaned[len(phrase) :].strip(" ,.!?")
        if lowered.endswith(" " + phrase):
            return True, cleaned[: -len(phrase)].strip(" ,.!?")
    return False, cleaned


def rule_to_tool_call(match: RuleMatch) -> ToolCall:
    """Map a deterministic voice rule to one registered built-in tool."""
    action, value = match.action, match.value
    if action == "stop":
        name, args = "voice.stop_listening", {}
    elif action == "delete":
        name, args = "mac.delete_selected", {}
    elif action == "close":
        name, args = "mac.close_app", {}
    elif action == "hide":
        name, args = "mac.key_combo", {"combo": "hide_app"}
    elif action == "key":
        keys = tuple(value) if isinstance(value, tuple) else ()
        key_to_combo = {
            ("command", "c"): "copy",
            ("command", "v"): "paste",
            ("command", "z"): "undo",
            ("command", "shift", "z"): "redo",
            ("command", "a"): "select_all",
        }
        combo = key_to_combo.get(keys)
        if combo is None:
            raise ValueError("unsupported deterministic keyboard shortcut")
        name, args = "mac.key_combo", {"combo": combo}
    elif action == "open":
        target = str(value)
        if target.startswith(("http://", "https://")):
            name, args = "mac.open_url", {"url": target}
        elif target.startswith(("/", "~", ".")):
            name, args = "mac.open_path", {"path": target}
        else:
            name, args = "mac.open_app", {"name": target}
    elif action == "search":
        name, args = "browser.search", {"query": str(value)}
    elif action == "type":
        name, args = "mac.type_text", {"text": str(value)}
    elif action == "play":
        name, args = "media.play", {}
    elif action == "pause":
        name, args = "media.pause", {}
    elif action == "mute":
        name, args = "mac.mute", {}
    elif action == "settings":
        name, args = "mac.open_app", {"name": "System Settings"}
    elif action == "volume":
        if not isinstance(value, int):
            raise ValueError("volume rule requires an integer")
        name, args = "mac.set_volume", {"value": value}
    elif action == "scroll":
        if not isinstance(value, int):
            raise ValueError("scroll rule requires an integer")
        name, args = "mac.scroll", {"amount": value}
    elif action == "screenshot":
        name, args = "mac.screenshot", {}
    elif action == "lock":
        name, args = "mac.lock_screen", {}
    else:
        raise ValueError(f"unsupported deterministic action: {action}")
    return ToolCall(uuid.uuid4().hex, name, args)


def rule_preapproved_by(match: RuleMatch) -> str | None:
    if match.action == "delete" and match.phrase in {"confirm delete", "yes delete"}:
        return "voice_phrase"
    return None
