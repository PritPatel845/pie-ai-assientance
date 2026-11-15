from __future__ import annotations

import pytest

from pie.brain.rules import match_rule, rule_preapproved_by, rule_to_tool_call


@pytest.mark.parametrize(
    ("phrase", "name", "args"),
    [
        ("stop listening", "voice.stop_listening", {}),
        ("confirm delete", "mac.delete_selected", {}),
        ("delete it", "mac.delete_selected", {}),
        ("close app", "mac.close_app", {}),
        ("hide app", "mac.key_combo", {"combo": "hide_app"}),
        ("copy", "mac.key_combo", {"combo": "copy"}),
        ("paste", "mac.key_combo", {"combo": "paste"}),
        ("undo", "mac.key_combo", {"combo": "undo"}),
        ("redo", "mac.key_combo", {"combo": "redo"}),
        ("select all", "mac.key_combo", {"combo": "select_all"}),
        ("play music", "media.play", {}),
        ("pause music", "media.pause", {}),
        ("mute audio", "mac.mute", {}),
        ("settings", "mac.open_app", {"name": "System Settings"}),
        ("screenshot", "mac.screenshot", {}),
        ("lock screen", "mac.lock_screen", {}),
        ("scroll up", "mac.scroll", {"amount": 5}),
        ("scroll down", "mac.scroll", {"amount": -5}),
        ("volume 25", "mac.set_volume", {"value": 25}),
        ("search cats", "browser.search", {"query": "cats"}),
        ("open Safari", "mac.open_app", {"name": "safari"}),
        ("open https://example.com", "mac.open_url", {"url": "https://example.com"}),
        ("open ~/Downloads", "mac.open_path", {"path": "~/downloads"}),
        ("type hello world", "mac.type_text", {"text": "hello world"}),
        ("open Notes", "mac.open_app", {"name": "notes"}),
    ],
)
def test_legacy_voice_phrase_maps_to_registered_tool(
    phrase: str, name: str, args: dict[str, object]
) -> None:
    match = match_rule(phrase)
    assert match is not None
    call = rule_to_tool_call(match)
    assert call.name == name
    assert call.args == args


@pytest.mark.parametrize("phrase", ["confirm delete", "yes delete"])
def test_explicit_delete_confirmation_is_preapproved(phrase: str) -> None:
    match = match_rule(phrase)
    assert match is not None
    assert rule_preapproved_by(match) == "voice_phrase"


def test_ambiguous_delete_phrase_still_requires_confirmation() -> None:
    match = match_rule("delete it")
    assert match is not None
    assert rule_preapproved_by(match) is None


def test_unsupported_keyboard_rule_fails_closed() -> None:
    from pie.brain.rules import RuleMatch

    with pytest.raises(ValueError):
        rule_to_tool_call(RuleMatch("key", ("command", "option", "x")))
