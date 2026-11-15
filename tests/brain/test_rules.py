from __future__ import annotations

import pytest

from pie.brain.rules import match_rule, wants_local


@pytest.mark.parametrize(("text", "expected"), [
    ("open Safari", ("open", "safari")),
    ("volume 25", ("volume", 25)),
    ("pause music", ("pause", None)),
])
def test_rule_matches_skip_model(text: str, expected: tuple[str, object]) -> None:
    match = match_rule(text)
    assert match is not None
    assert (match.action, match.value) == expected


@pytest.mark.parametrize(("text", "expected"), [
    ("use local what is 2+2", (True, "what is 2+2")),
    ("what is 2+2 offline", (True, "what is 2+2")),
    ("locally", (True, "")),
    ("local restaurants near me", (False, "local restaurants near me")),
    ("open the local folder", (False, "open the local folder")),
])
def test_local_directive_is_only_at_edges(text: str, expected: tuple[bool, str]) -> None:
    assert wants_local(text) == expected
