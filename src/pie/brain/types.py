from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, Sequence


@dataclass(frozen=True, slots=True)
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: str | None = None
    tool_calls: tuple[ToolCall, ...] | None = None


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True, slots=True)
class ProviderReply:
    text: str
    tool_calls: tuple[ToolCall, ...] = ()
    usage: Usage | None = None
    stop_reason: str = "stop"


@dataclass(frozen=True, slots=True)
class RouterResult:
    route: Literal["rule", "cloud", "local"]
    provider: str | None
    text: str
    tool_calls_made: int
    ok: bool
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    tier: int = 0


@dataclass(frozen=True, slots=True)
class ToolResult:
    ok: bool
    output: Any = None
    error: str | None = None


class ProviderError(Exception):
    def __init__(self, provider: str, message: str = "") -> None:
        self.provider = provider
        super().__init__(message or provider)


class QuotaExhausted(ProviderError):
    def __init__(self, provider: str, reset_at: float | None = None) -> None:
        self.reset_at = reset_at
        super().__init__(provider, "quota exhausted")


class RateLimited(ProviderError):
    def __init__(self, provider: str, retry_after: float = 0.0) -> None:
        self.retry_after = retry_after
        super().__init__(provider, "rate limited")


class ProviderUnavailable(ProviderError):
    pass


class AuthError(ProviderError):
    pass


class Provider(Protocol):
    name: str
    kind: Literal["cloud", "local"]

    async def complete(
        self,
        messages: Sequence[Message],
        tools: list[ToolSpec],
        *,
        max_tokens: int,
        timeout_s: float,
    ) -> ProviderReply: ...

    async def healthcheck(self) -> bool: ...
