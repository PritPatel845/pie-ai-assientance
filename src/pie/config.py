from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class AppConfig:
    name: str = "pie"
    log_level: str = "INFO"


@dataclass(frozen=True, slots=True)
class GestureConfig:
    camera: int = 0
    preview: bool = True
    arm_hold_seconds: float = 2.0
    steer_sensitivity: float = 0.004
    state_hz: int = 10
    model_path: str = ""


@dataclass(frozen=True, slots=True)
class VoiceConfig:
    enabled: bool = True
    wake_words: tuple[str, ...] = ("pie", "hey pie", "pi", "jr", "j r", "jay r", "jarvis")
    listen_seconds: int = 20
    language: str = "en"


@dataclass(frozen=True, slots=True)
class UiConfig:
    host: str = "127.0.0.1"
    port: int = 8765


@dataclass(frozen=True, slots=True)
class Config:
    app: AppConfig = AppConfig()
    gesture: GestureConfig = GestureConfig()
    voice: VoiceConfig = VoiceConfig()
    ui: UiConfig = UiConfig()


_DEFAULTS: dict[str, dict[str, Any]] = {
    "app": {"name": "pie", "log_level": "INFO"},
    "gesture": {
        "camera": 0,
        "preview": True,
        "arm_hold_seconds": 2.0,
        "steer_sensitivity": 0.004,
        "state_hz": 10,
        "model_path": "",
    },
    "voice": {
        "enabled": True,
        "wake_words": ["pie", "hey pie", "pi", "jr", "j r", "jay r", "jarvis"],
        "listen_seconds": 20,
        "language": "en",
    },
    "ui": {"host": "127.0.0.1", "port": 8765},
}
_TYPES = {
    section: {key: type(value) for key, value in values.items()}
    for section, values in _DEFAULTS.items()
}


def _merge(target: dict[str, dict[str, Any]], source: dict[str, Any]) -> None:
    unknown_sections = set(source) - set(target)
    if unknown_sections:
        raise ValueError(f"Unknown config section(s): {', '.join(sorted(unknown_sections))}")
    for section, values in source.items():
        if not isinstance(values, dict):
            raise ValueError(f"Config section {section} must be a table")
        unknown = set(values) - set(target[section])
        if unknown:
            raise ValueError(f"Unknown config key(s) in {section}: {', '.join(sorted(unknown))}")
        for key, value in values.items():
            expected = _TYPES[section][key]
            if expected is int and isinstance(value, bool):
                raise ValueError(f"{section}.{key} must be int")
            if not isinstance(value, expected):
                raise ValueError(f"{section}.{key} must be {expected.__name__}")
            target[section][key] = value


def load_config(
    path: Path | None = None,
    *,
    environ: dict[str, str] | None = None,
    cli_overrides: dict[str, dict[str, Any]] | None = None,
) -> Config:
    data = {section: dict(values) for section, values in _DEFAULTS.items()}
    user_path = path or Path.home() / ".pie" / "config.toml"
    if user_path.is_file():
        with user_path.open("rb") as handle:
            _merge(data, tomllib.load(handle))
    env = os.environ if environ is None else environ
    for section, values in data.items():
        for key, old in tuple(values.items()):
            env_key = f"PIE_{section.upper()}_{key.upper()}"
            if env_key not in env:
                continue
            raw = env[env_key]
            if isinstance(old, bool):
                if raw.lower() not in {"true", "false"}:
                    raise ValueError(f"{env_key} must be true or false")
                values[key] = raw.lower() == "true"
            elif isinstance(old, int):
                values[key] = int(raw)
            elif isinstance(old, float):
                values[key] = float(raw)
            elif isinstance(old, list):
                raise ValueError(f"{env_key} does not support list overrides")
            else:
                values[key] = raw
    if cli_overrides:
        _merge(data, cli_overrides)
    data["voice"]["wake_words"] = tuple(data["voice"]["wake_words"])
    config = Config(
        AppConfig(**data["app"]),
        GestureConfig(**data["gesture"]),
        VoiceConfig(**data["voice"]),
        UiConfig(**data["ui"]),
    )
    if config.gesture.state_hz < 1 or config.gesture.state_hz > 60:
        raise ValueError("gesture.state_hz must be between 1 and 60")
    if config.ui.port < 1 or config.ui.port > 65535:
        raise ValueError("ui.port must be between 1 and 65535")
    if config.voice.listen_seconds < 5:
        raise ValueError("voice.listen_seconds must be at least 5")
    return config
