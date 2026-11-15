from __future__ import annotations

import pytest

from pie.inputs.voice.tts import sanitise_speech


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  hello   world  ", "hello world"),
        ("hello\nworld", "hello world"),
        ("hello\x00world", "hello world"),
        ("", ""),
        ("x" * 1200, "x" * 1000),
    ],
)
def test_speech_sanitiser(raw: str, expected: str) -> None:
    assert sanitise_speech(raw) == expected
