import pytest

from pie.core.config import load_config


def test_defaults_and_typed_environment() -> None:
    config = load_config(environ={"PIE_UI_PORT": "9000", "PIE_VOICE_ENABLED": "false"})
    assert config.ui.port == 9000
    assert config.voice.enabled is False


def test_unknown_config_keys_rejected(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[voice]\nunknown = true\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown config key"):
        load_config(path)


def test_invalid_environment_boolean_rejected() -> None:
    with pytest.raises(ValueError, match="expected true or false"):
        load_config(environ={"PIE_VOICE_ENABLED": "sometimes"})


def test_range_validation() -> None:
    with pytest.raises(ValueError, match="port"):
        load_config(environ={"PIE_UI_PORT": "70000"})
