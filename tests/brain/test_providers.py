from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import pytest

from pie.brain.providers import UnavailableProvider
from pie.brain.providers.anthropic_api import _raise_vendor_error
from pie.brain.providers.claude_cli import ClaudeCliProvider
from pie.brain.providers.codex_cli import CodexCliProvider
from pie.brain.types import (
    AuthError,
    Message,
    ProviderUnavailable,
    QuotaExhausted,
    RateLimited,
)


class AuthenticationError(Exception):
    pass


class RateLimitError(Exception):
    def __init__(self, retry_after: str = "2.5") -> None:
        super().__init__("too many requests")
        self.response = type("Response", (), {"headers": {"retry-after": retry_after}})()


class APIConnectionError(Exception):
    pass


class InternalServerError(Exception):
    status_code = 503


def test_vendor_auth_error_mapping() -> None:
    with pytest.raises(AuthError):
        _raise_vendor_error("anthropic", AuthenticationError("invalid key"))


def test_vendor_rate_limit_preserves_retry_after() -> None:
    with pytest.raises(RateLimited) as caught:
        _raise_vendor_error("openai", RateLimitError())
    assert caught.value.retry_after == 2.5


def test_vendor_billing_error_maps_to_quota() -> None:
    with pytest.raises(QuotaExhausted):
        _raise_vendor_error("anthropic", Exception("credit balance too low"))


@pytest.mark.parametrize("error", [APIConnectionError("offline"), InternalServerError("server")])
def test_vendor_network_and_server_errors_map_to_unavailable(error: Exception) -> None:
    with pytest.raises(ProviderUnavailable):
        _raise_vendor_error("openai", error)


@pytest.mark.parametrize("provider", [ClaudeCliProvider(), CodexCliProvider()])
def test_cli_providers_are_safe_stubs_until_sandbox_flags_are_verified(provider: object) -> None:
    async def scenario() -> None:
        assert await provider.healthcheck()  # type: ignore[attr-defined]
        with pytest.raises(ProviderUnavailable, match="unsafe: cannot sandbox"):
            await provider.complete(  # type: ignore[attr-defined]
                [Message("user", "test")], [], max_tokens=8, timeout_s=1.0
            )

    asyncio.run(scenario())

def test_missing_cloud_credential_stays_in_chain_and_raises_auth_error() -> None:
    async def scenario() -> None:
        provider = UnavailableProvider(
            "anthropic", AuthError("anthropic", "API key not configured")
        )
        assert await provider.healthcheck()
        with pytest.raises(AuthError):
            await provider.complete(
                [Message("user", "test")], [], max_tokens=8, timeout_s=1.0
            )

    asyncio.run(scenario())

def test_vendor_http_date_retry_after_is_parsed() -> None:
    retry_at = datetime.now(timezone.utc) + timedelta(seconds=30)
    error = RateLimitError(format_datetime(retry_at, usegmt=True))

    with pytest.raises(RateLimited) as caught:
        _raise_vendor_error("anthropic", error)

    assert 0 < caught.value.retry_after <= 30
