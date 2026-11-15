from __future__ import annotations

import importlib
import os
from getpass import getpass
from typing import Any

_SERVICE = "pie"


def _keyring() -> Any | None:
    try:
        return importlib.import_module("keyring")
    except ImportError:
        return None


def get_api_key(provider: str) -> str | None:
    env_name = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}.get(provider)
    backend = _keyring()
    stored = backend.get_password(_SERVICE, provider) if backend is not None else None
    return stored or (os.environ.get(env_name) if env_name else None)


def set_api_key(provider: str, *, prompt: str | None = None) -> None:
    if provider not in {"anthropic", "openai"}:
        raise ValueError("provider must be anthropic or openai")
    backend = _keyring()
    if backend is None:
        raise RuntimeError("Install the optional brain dependencies to use the system Keychain")
    secret = getpass(prompt or f"{provider} API key: ")
    if not secret.strip():
        raise ValueError("API key cannot be empty")
    backend.set_password(_SERVICE, provider, secret.strip())
