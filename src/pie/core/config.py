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
    wake_words: tuple[str, ...] = ("pie", "hey pie")
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
    "gesture": {"camera": 0, "preview": True, "arm_hold_seconds": 2.0,
                "steer_sensitivity": 0.004, "state_hz": 10, "model_path": ""},
    "voice": {"enabled": True, "wake_words": ["pie", "hey pie"], "listen_seconds": 20,
              "language": "en"},
    "ui": {"host": "127.0.0.1", "port": 8765},
}
_TYPES: dict[str, dict[str, type]] = {
    section: {key: type(value) for key, value in values.items()}
    for section, values in _DEFAULTS.items()
}
_ENV = {
    "PIE_APP_NAME": ("app", "name"), "PIE_LOG_LEVEL": ("app", "log_level"),
    "PIE_GESTURE_CAMERA": ("gesture", "camera"),
    "PIE_GESTURE_PREVIEW": ("gesture", "preview"),
    "PIE_GESTURE_STATE_HZ": ("gesture", "state_hz"),
    "PIE_VOICE_ENABLED": ("voice", "enabled"),
    "PIE_VOICE_LANGUAGE": ("voice", "language"),
    "PIE_UI_HOST": ("ui", "host"), "PIE_UI_PORT": ("ui", "port"),
}


def _coerce(value: str, expected: type, key: str) -> Any:
    try:
        if expected is bool:
            lowered = value.lower()
            if lowered not in {"true", "false"}:
                raise ValueError("expected true or false")
            return lowered == "true"
        if expected is int:
            return int(value)
        if expected is float:
            return float(value)
        return value
    except ValueError as exc:
        raise ValueError(f"invalid value for {key}: {exc}") from exc


def load_config(path: Path | None = None, *, environ: dict[str, str] | None = None) -> Config:
    """Load packaged defaults, optional user TOML, then strict environment overrides."""
    data = {section: dict(values) for section, values in _DEFAULTS.items()}
    if path is not None and path.expanduser().exists():
        with path.expanduser().open("rb") as handle:
            user = tomllib.load(handle)
        _merge(data, user, "config")
    env = os.environ if environ is None else environ
    for name, (section, key) in _ENV.items():
        if name in env:
            data[section][key] = _coerce(env[name], _TYPES[section][key], name)
    app = AppConfig(**data["app"])
    gesture_data = data["gesture"]
    if gesture_data["model_path"]:
        gesture_data["model_path"] = str(Path(gesture_data["model_path"]).expanduser())
    gesture = GestureConfig(**gesture_data)
    voice_data = data["voice"]
    voice_data["wake_words"] = tuple(voice_data["wake_words"])
    voice = VoiceConfig(**voice_data)
    ui = UiConfig(**data["ui"])
    if not 1 <= gesture.state_hz <= 60:
        raise ValueError("gesture.state_hz must be between 1 and 60")
    if not 1 <= ui.port <= 65535:
        raise ValueError("ui.port must be between 1 and 65535")
    if voice.listen_seconds < 5:
        raise ValueError("voice.listen_seconds must be at least 5")
    return Config(app, gesture, voice, ui)


def _merge(target: dict[str, dict[str, Any]], source: dict[str, Any], label: str) -> None:
    unknown_sections = set(source) - set(target)
    if unknown_sections:
        raise ValueError(f"unknown {label} section(s): {', '.join(sorted(unknown_sections))}")
    for section, values in source.items():
        if not isinstance(values, dict):
            raise ValueError(f"{label} section {section} must be a table")
        unknown_keys = set(values) - set(target[section])
        if unknown_keys:
            raise ValueError(f"unknown {label} key(s) in {section}: {', '.join(sorted(unknown_keys))}")
        for key, value in values.items():
            expected = _TYPES[section][key]
            if expected is int and isinstance(value, bool):
                raise ValueError(f"{section}.{key} must be int")
            if not isinstance(value, expected):
                raise ValueError(f"{section}.{key} must be {expected.__name__}")
            target[section][key] = value
