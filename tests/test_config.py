from __future__ import annotations

import pytest

from pie.config import load_config


def test_config_defaults_and_environment_override() -> None:
    config = load_config(environ={"PIE_UI_PORT": "9000", "PIE_VOICE_ENABLED": "false"})
    assert config.ui.port == 9000
    assert config.voice.enabled is False


def test_unknown_config_key_is_rejected(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[voice]\nunknown = true\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown|Unknown"):
        load_config(path)


def test_invalid_environment_boolean_is_rejected() -> None:
    with pytest.raises(ValueError, match="bool"):
        load_config(environ={"PIE_VOICE_ENABLED": "maybe"})


def test_environment_boolean_spellings_and_list_override() -> None:
    config = load_config(environ={
        "PIE_VOICE_ENABLED": "yes",
        "PIE_VOICE_WAKE_WORDS": '["pie", "hey pie"]',
    })
    assert config.voice.enabled is True
    assert config.voice.wake_words == ("pie", "hey pie")


def test_unknown_environment_key_for_known_section_is_rejected() -> None:
    with pytest.raises(ValueError, match="PIE_GESTURE_UNKNOWN"):
        load_config(environ={"PIE_GESTURE_UNKNOWN": "1"})


def test_config_precedence_and_path_expansion(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        '[gesture]\\n'
        'camera = 2\\n'
        'model_path = "~/models/hand.task"\\n',
        encoding="utf-8",
    )
    config = load_config(
        path,
        environ={"PIE_GESTURE_CAMERA": "3"},
        cli_overrides={"gesture": {"camera": 4}},
    )
    assert config.gesture.camera == 4
    assert config.gesture.model_path == str(tmp_path.home() / "models" / "hand.task")
