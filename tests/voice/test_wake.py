from __future__ import annotations

import pytest

from pie.inputs.voice.wake import TextWake


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Pie open Safari", "open safari"),
        ("hey pie open Safari", "open safari"),
        ("PI, open Safari", "open safari"),
        ("jr open Safari", "open safari"),
        ("j r open Safari", "open safari"),
        ("jay r open Safari", "open safari"),
        ("jarvis open Safari", "open safari"),
        ("pai open Safari", "open safari"),
        ("pye open Safari", "open safari"),
        ("hi pie open Safari", "open safari"),
        ("hey pi open Safari", "open safari"),
        ("pie chart please", "chart please"),
        ("Pie", ""),
        ("hey pie", ""),
        ("pizza please", None),
        ("pied piper", None),
        ("apple pie recipe", None),
        ("I like pie", None),
        ("the pie chart", None),
        ("a pizza pie recipe", None),
        ("spicy food", None),
        ("open Safari pie", None),
        ("please open Safari", None),
        ("hey, pie open Safari", "open safari"),
        ("PI! volume 20", "volume 20"),
        ("jarvis, pause music", "pause music"),
        ("JR. screenshot", "screenshot"),
        ("pai, mute", "mute"),
        ("pye please search cats", "please search cats"),
        ("hi pie, lock screen", "lock screen"),
        ("", None),
        ("   ", None),
    ],
)
def test_wake_detector_table(text: str, expected: str | None) -> None:
    assert TextWake().check(text) == expected
