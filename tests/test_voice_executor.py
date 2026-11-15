"""LegacyRuleExecutor and VoiceController behaviour follow Phase 0S §3.7 (PDF p. 22)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pie.inputs.voice.executor import LegacyRuleExecutor, VoiceController


class FakeController:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        return lambda *args: self.calls.append((name, *args)) or True


def test_executor_maps_parsed_command_to_adapter() -> None:
    fake = FakeController()
    executor = LegacyRuleExecutor(fake)
    assert executor.execute("open safari")
    assert fake.calls == [("open_application_or_item", "safari")]


def test_no_actions_does_not_touch_adapter() -> None:
    fake = FakeController()
    executor = LegacyRuleExecutor(fake, no_actions=True)
    assert executor.execute("open safari")
    assert fake.calls == []


def test_voice_controller_redacts_type_history(tmp_path) -> None:
    from pie.inputs.gesture.learning import LearningEngine

    learning = LearningEngine(tmp_path)
    controller = VoiceController(FakeController(), learning_engine=learning)
    controller.execute("type my secret")
    assert learning._voice == ["type <redacted>"]



@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("delete it", ("delete_selected",)),
        ("close app", ("close_frontmost",)),
        ("hide app", ("hide_frontmost",)),
        ("undo", ("key_combo", "command", "z")),
        ("open https://example.com", ("open_target", "https://example.com")),
        ("open ~/Documents", ("open_target", str(Path("~/Documents").expanduser()))),
        ("open safari", ("open_application_or_item", "safari")),
        ("search two words", ("open_target", "https://www.google.com/search?q=two+words")),
        ("type hello world", ("type_text", "hello world")),
        ("play music", ("play_media",)),
        ("pause music", ("stop_media",)),
        ("mute audio", ("mute",)),
        ("open settings", ("open_system_settings",)),
        ("volume 120", ("set_volume", 100)),
        ("scroll down", ("scroll", -5)),
        ("take a screenshot", ("screenshot",)),
        ("lock screen", ("lock_screen",)),
    ],
)
def test_legacy_executor_preserves_each_rule_mapping(phrase, expected) -> None:
    fake = FakeController()
    assert LegacyRuleExecutor(fake).execute(phrase)
    assert fake.calls == [expected]


def test_stop_phrase_returns_false_without_controller_action() -> None:
    fake = FakeController()
    assert LegacyRuleExecutor(fake).execute("stop listening") is False
    assert fake.calls == []


def test_voice_controller_start_is_a_phase_2a_stub() -> None:
    controller = VoiceController(FakeController())
    assert controller.start() is None
