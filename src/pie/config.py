from __future__ import annotations

import json
import os
import sys
import tomllib
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

from pie.paths import config_path


# fmt: off
class ConfigError(ValueError):
    """Raised when a configuration source contains an invalid value."""


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
    bindings: dict[str, str] = field(
        default_factory=lambda: {
            "thumb_up": "media.play",
            "thumb_down": "media.pause",
            "palm_push": "mac.mute",
        }
    )
    bindings_via_tools: bool = True


@dataclass(frozen=True, slots=True)
class VoiceConfig:
    enabled: bool = True
    wake_words: tuple[str, ...] = (
        "hey pie",
        "pie",
        "pi",
        "jr",
        "j r",
        "jay r",
        "jarvis",
    )
    listen_seconds: int = 20
    language: str = "en"
    stt_backend: str = "auto"
    stt_model: str = "base.en"
    input_device: str = ""
    vad_threshold: float = 0.015
    vad_min_speech_ms: int = 150
    vad_end_silence_ms: int = 600
    vad_max_utterance_s: float = 12.0
    stt_idle_unload_s: int = 300
    tts_enabled: bool = True
    tts_voice: str = "Samantha"
    tts_rate: int = 185
    allow_cloud_stt: bool = False
    debug_save_audio: bool = False


@dataclass(frozen=True, slots=True)
class UiConfig:
    host: str = "127.0.0.1"
    port: int = 8765


@dataclass(frozen=True, slots=True)
class BrainConfig:
    enabled: bool = True
    cloud_order: tuple[str, ...] = ("anthropic", "openai")
    cli_providers_enabled: bool = False
    anthropic_model: str = ""
    openai_model: str = ""
    local_backend: str = "auto"
    local_model: str = ""
    max_steps: int = 8
    total_timeout_s: int = 90
    provider_timeout_s: int = 45
    context_turns: int = 6
    context_ttl_s: int = 600
    default_cooldown_s: int = 3600
    rate_limit_max_wait_s: int = 8
    local_max_ram_gb: float = 6.0
    local_keep_alive: str = "2m"


@dataclass(frozen=True, slots=True)
class SafetyConfig:
    sandbox_dir: str = "~/PieWorkspace"
    allowed_folders: tuple[str, ...] = ("~/Desktop", "~/Documents", "~/Downloads", "~/PieWorkspace")
    confirm_timeout_s: int = 45
    max_calls_per_10s: int = 10
    max_confirm_prompts_per_min: int = 3
    audit_path: str = "~/.pie/logs/audit.jsonl"


@dataclass(frozen=True, slots=True)
class ToolsConfig:
    dry_run: bool = False
    disabled: tuple[str, ...] = ()
    result_max_chars: int = 20000


@dataclass(frozen=True, slots=True)
class Config:
    app: AppConfig = AppConfig()
    gesture: GestureConfig = GestureConfig()
    voice: VoiceConfig = VoiceConfig()
    ui: UiConfig = UiConfig()
    brain: BrainConfig = BrainConfig()
    safety: SafetyConfig = SafetyConfig()
    tools: ToolsConfig = ToolsConfig()


_DEFAULTS: dict[str, dict[str, Any]] = {
    "app": {"name": "pie", "log_level": "INFO"},
    "gesture": {
        "camera": 0,
        "preview": True,
        "arm_hold_seconds": 2.0,
        "steer_sensitivity": 0.004,
        "state_hz": 10,
        "model_path": "",
        "bindings": {
            "thumb_up": "media.play",
            "thumb_down": "media.pause",
            "palm_push": "mac.mute",
        },
        "bindings_via_tools": True,
    },
    "voice": {
        "enabled": True,
        "wake_words": ["hey pie", "pie", "pi", "jr", "j r", "jay r", "jarvis"],
        "listen_seconds": 20,
        "language": "en",
        "stt_backend": "auto",
        "stt_model": "base.en",
        "input_device": "",
        "vad_threshold": 0.015,
        "vad_min_speech_ms": 150,
        "vad_end_silence_ms": 600,
        "vad_max_utterance_s": 12.0,
        "stt_idle_unload_s": 300,
        "tts_enabled": True,
        "tts_voice": "Samantha",
        "tts_rate": 185,
        "allow_cloud_stt": False,
        "debug_save_audio": False,
    },
    "ui": {"host": "127.0.0.1", "port": 8765},
    "brain": {
        "enabled": True,
        "cloud_order": ["anthropic", "openai"],
        "cli_providers_enabled": False,
        "anthropic_model": "",
        "openai_model": "",
        "local_backend": "auto",
        "local_model": "",
        "max_steps": 8,
        "total_timeout_s": 90,
        "provider_timeout_s": 45,
        "context_turns": 6,
        "context_ttl_s": 600,
        "default_cooldown_s": 3600,
        "rate_limit_max_wait_s": 8,
        "local_max_ram_gb": 6.0,
        "local_keep_alive": "2m",
    },
    "safety": {
        "sandbox_dir": "~/PieWorkspace",
        "allowed_folders": ["~/Desktop", "~/Documents", "~/Downloads", "~/PieWorkspace"],
        "confirm_timeout_s": 45,
        "max_calls_per_10s": 10,
        "max_confirm_prompts_per_min": 3,
        "audit_path": "~/.pie/logs/audit.jsonl",
    },
    "tools": {"dry_run": False, "disabled": [], "result_max_chars": 20000},
}
_TYPES = {
    section: {key: type(value) for key, value in values.items()}
    for section, values in _DEFAULTS.items()
}


def _merge(target: dict[str, dict[str, Any]], source: dict[str, Any]) -> None:
    unknown_sections = set(source) - set(target)
    if unknown_sections:
        raise ConfigError(
            f"Unknown config section(s): {', '.join(sorted(unknown_sections))}",
        )
    for section, values in source.items():
        if not isinstance(values, dict):
            raise ConfigError(f"Config section {section} must be a table")
        unknown = set(values) - set(target[section])
        if unknown:
            raise ConfigError(
                f"Unknown config key(s) in {section}: {', '.join(sorted(unknown))}",
            )
        for key, value in values.items():
            expected = _TYPES[section][key]
            if expected is int and isinstance(value, bool):
                raise ConfigError(f"{section}.{key} must be int")
            if not isinstance(value, expected):
                raise ConfigError(f"{section}.{key} must be {expected.__name__}")
            target[section][key] = value


def _parse_environment_value(name: str, raw: str, current: Any) -> Any:
    if isinstance(current, bool):
        lowered = raw.lower()
        if lowered not in {"true", "false", "1", "0", "yes", "no"}:
            raise ConfigError(f"{name} must be bool (true/false/1/0/yes/no)")
        return lowered in {"true", "1", "yes"}
    if isinstance(current, int):
        try:
            return int(raw)
        except ValueError as exc:
            raise ConfigError(f"{name} must be int") from exc
    if isinstance(current, float):
        try:
            return float(raw)
        except ValueError as exc:
            raise ConfigError(f"{name} must be float") from exc
    if isinstance(current, dict):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"{name} must be a JSON object") from exc
        if not isinstance(value, dict):
            raise ConfigError(f"{name} must be a JSON object")
        return value
    if isinstance(current, list):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"{name} must be a JSON array") from exc
        valid_string_list = isinstance(value, list) and all(
            isinstance(item, str) for item in value
        )
        if not valid_string_list:
            raise ConfigError(f"{name} must be a JSON array of strings")
        return value
    return raw


def load_config(
    path: Path | None = None,
    *,
    environ: dict[str, str] | None = None,
    cli_overrides: dict[str, dict[str, Any]] | None = None,
) -> Config:
    data = {section: dict(values) for section, values in _DEFAULTS.items()}
    packaged_default = resources.files("pie").joinpath(
        "..", "..", "..", "..", "config", "pie.default.toml"
    )
    if packaged_default.is_file():
        with packaged_default.open("rb") as handle:
            _merge(data, tomllib.load(handle))
    else:
        candidates = (
            Path(__file__).resolve().parents[2] / "config" / "pie.default.toml",
            Path(sys.prefix) / "config" / "pie.default.toml",
        )
        for defaults_path in candidates:
            if defaults_path.is_file():
                with defaults_path.open("rb") as handle:
                    _merge(data, tomllib.load(handle))
                break

    user_path = path or config_path()
    if user_path.is_file():
        with user_path.open("rb") as handle:
            _merge(data, tomllib.load(handle))

    env = os.environ if environ is None else environ
    known_env = {
        f"PIE_{section.upper()}_{key.upper()}"
        for section, values in data.items()
        for key in values
    }
    for name, raw in env.items():
        if name in known_env:
            section, key = name.removeprefix("PIE_").lower().split("_", 1)
            data[section][key] = _parse_environment_value(name, raw, data[section][key])
        elif name.startswith("PIE_"):
            raise ConfigError(f"Unknown environment variable: {name}")

    if cli_overrides:
        _merge(data, cli_overrides)

    data["voice"]["wake_words"] = tuple(data["voice"]["wake_words"])
    data["brain"]["cloud_order"] = tuple(data["brain"]["cloud_order"])
    data["safety"]["allowed_folders"] = tuple(data["safety"]["allowed_folders"])
    data["tools"]["disabled"] = tuple(data["tools"]["disabled"])
    bindings = data["gesture"]["bindings"]
    if not isinstance(bindings, dict) or any(
        key not in {"thumb_up", "thumb_down", "palm_push"} or not isinstance(value, str)
        for key, value in bindings.items()
    ):
        raise ConfigError("gesture.bindings must map supported gesture names to tool names")
    model_path = str(data["gesture"]["model_path"])
    if model_path:
        data["gesture"]["model_path"] = str(Path(model_path).expanduser())

    config = Config(
        AppConfig(**data["app"]),
        GestureConfig(**data["gesture"]),
        VoiceConfig(**data["voice"]),
        UiConfig(**data["ui"]),
        BrainConfig(**data["brain"]),
        SafetyConfig(**data["safety"]),
        ToolsConfig(**data["tools"]),
    )
    if not 1 <= config.gesture.state_hz <= 60:
        raise ConfigError("gesture.state_hz must be between 1 and 60")
    if not 1 <= config.ui.port <= 65535:
        raise ConfigError("ui.port must be between 1 and 65535")
    if config.voice.listen_seconds < 5:
        raise ConfigError("voice.listen_seconds must be at least 5")
    if config.voice.stt_backend not in {"auto", "mlx", "whispercpp", "google"}:
        raise ConfigError("voice.stt_backend must be auto, mlx, whispercpp, or google")
    if config.voice.vad_threshold <= 0:
        raise ConfigError("voice.vad_threshold must be positive")
    if config.voice.vad_min_speech_ms < 1 or config.voice.vad_end_silence_ms < 1:
        raise ConfigError("voice VAD durations must be positive")
    if config.voice.vad_max_utterance_s <= 0 or config.voice.stt_idle_unload_s < 0:
        raise ConfigError("voice utterance and unload durations are invalid")
    if not 1 <= config.voice.tts_rate <= 500:
        raise ConfigError("voice.tts_rate must be between 1 and 500")
    if config.brain.local_backend not in {"auto", "ollama", "mlx"}:
        raise ConfigError("brain.local_backend must be auto, ollama, or mlx")
    if (
        not config.brain.cloud_order
        or len(set(config.brain.cloud_order)) != len(config.brain.cloud_order)
        or any(provider not in {"anthropic", "openai"} for provider in config.brain.cloud_order)
    ):
        raise ConfigError("brain.cloud_order must contain anthropic and/or openai")
    if min(
        config.brain.max_steps,
        config.brain.total_timeout_s,
        config.brain.provider_timeout_s,
        config.brain.context_turns,
        config.brain.context_ttl_s,
        config.brain.default_cooldown_s,
        config.brain.rate_limit_max_wait_s,
    ) < 1 or config.brain.local_max_ram_gb <= 0:
        raise ConfigError("brain limits must be positive")
    if config.gesture.arm_hold_seconds <= 0:
        raise ConfigError("gesture.arm_hold_seconds must be positive")
    if min(config.safety.confirm_timeout_s, config.safety.max_calls_per_10s,
           config.safety.max_confirm_prompts_per_min, config.tools.result_max_chars) < 1:
        raise ConfigError("safety and tools limits must be positive")
    return config

# fmt: on
