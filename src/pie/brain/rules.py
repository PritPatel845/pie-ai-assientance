from __future__ import annotations

from dataclasses import dataclass

from pie.inputs.voice.commands import parse_voice_command


@dataclass(frozen=True, slots=True)
class RuleMatch:
    action: str
    value: object | None


def match_rule(text: str) -> RuleMatch | None:
    parsed = parse_voice_command(text)
    if parsed is None:
        return None
    return RuleMatch(parsed[0], parsed[1])


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
