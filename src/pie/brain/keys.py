from __future__ import annotations

import os
from getpass import getpass

import keyring

_SERVICE = "pie"


def get_api_key(provider: str) -> str | None:
    env_name = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}.get(provider)
    stored = keyring.get_password(_SERVICE, provider)
    return stored or (os.environ.get(env_name) if env_name else None)


def set_api_key(provider: str, *, prompt: str | None = None) -> None:
    if provider not in {"anthropic", "openai"}:
        raise ValueError("provider must be anthropic or openai")
    secret = getpass(prompt or f"{provider} API key: ")
    if not secret.strip():
        raise ValueError("API key cannot be empty")
    keyring.set_password(_SERVICE, provider, secret.strip())
