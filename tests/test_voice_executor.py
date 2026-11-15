from __future__ import annotations

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
