from __future__ import annotations

import difflib
import re
from collections.abc import Sequence
from typing import Protocol

from pie.inputs.voice.commands import VOICE_WAKE_WORDS, extract_wake_command


class WakeDetector(Protocol):
    def check(self, text: str) -> str | None: ...


class TextWake:
    """Text wake detector with conservative first-one/two-token fuzzy matching."""

    _MISHEARINGS = ("pie", "pi", "pai", "pye", "hey pi", "hey pie", "hi pie")

    def __init__(self, wake_words: Sequence[str] = VOICE_WAKE_WORDS) -> None:
        self.wake_words = tuple(word.lower().strip() for word in wake_words if word.strip())
        self._phrases = tuple(dict.fromkeys((*self.wake_words, *self._MISHEARINGS)))

    def check(self, text: str) -> str | None:
        cleaned = re.sub(r"\s+", " ", text.strip().lower())
        if not cleaned:
            return None
        exact = extract_wake_command(cleaned)
        if exact is not None:
            return exact

        tokens = re.findall(r"[\w']+", cleaned)
        candidates = sorted(self._phrases, key=lambda value: len(value.split()), reverse=True)
        for phrase in candidates:
            expected = phrase.split()
            count = len(expected)
            if count not in (1, 2) or len(tokens) < count:
                continue
            actual = " ".join(tokens[:count])
            ratio = difflib.SequenceMatcher(None, actual, phrase).ratio()
            boundary_ok = len(tokens) == count or tokens[count - 1] in {expected[-1], "pie"}
            if ratio >= 0.84 and boundary_ok:
                return " ".join(tokens[count:]).strip()
        return None
