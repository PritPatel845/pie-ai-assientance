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
    with pytest.raises(ValueError, match="true or false"):
        load_config(environ={"PIE_VOICE_ENABLED": "yes"})
