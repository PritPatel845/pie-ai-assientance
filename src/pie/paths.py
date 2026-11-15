from __future__ import annotations

from pathlib import Path


def pie_home() -> Path:
    return Path.home() / ".pie"


def config_path() -> Path:
    return pie_home() / "config.toml"


def state_dir(*, create: bool = False) -> Path:
    return _directory("state", create)


def logs_dir(*, create: bool = False) -> Path:
    return _directory("logs", create)


def models_dir(*, create: bool = False) -> Path:
    return _directory("models", create)


def learning_dir(*, create: bool = False) -> Path:
    # Path B starts clean: Phase 0S does not import legacy Jarvis data.
    return _directory("learning", create)


def _directory(name: str, create: bool) -> Path:
    path = pie_home() / name
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path
