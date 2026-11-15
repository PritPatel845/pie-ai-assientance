from __future__ import annotations

import pytest

from pie.inputs.voice.wake import TextWake


@pytest.mark.parametrize(
    "transcript",
    [
        "why use local model what is the capital of France",
        "why is the sky blue",
        "why should I open Safari",
        "I wonder why this happened",
    ],
)
def test_why_homophone_never_activates_pie(transcript: str) -> None:
    # "why" is a plausible ASR substitution for "Pie", but accepting it as a
    # wake word would activate on ordinary questions and conversations.
    assert TextWake().check(transcript) is None
