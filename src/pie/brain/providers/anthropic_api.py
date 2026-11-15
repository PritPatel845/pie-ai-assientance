from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from pie.brain.keys import get_api_key
from pie.brain.types import (
    AuthError,
    Message,
    ProviderReply,
    ProviderUnavailable,
    QuotaExhausted,
    RateLimited,
    ToolCall,
    ToolSpec,
    Usage,
)


class AnthropicProvider:
    name = "anthropic"
    kind = "cloud"

    def __init__(self, model: str, *, client: Any | None = None) -> None:
        self.model = model
        if client is None:
            from anthropic import AsyncAnthropic

            key = get_api_key("anthropic")
            if not key:
                raise AuthError(self.name, "API key not configured")
            client = AsyncAnthropic(api_key=key)
        self.client = client

    async def healthcheck(self) -> bool:
        return bool(self.model)

    async def complete(
        self,
        messages: Sequence[Message],
        tools: list[ToolSpec],
        *,
        max_tokens: int,
        timeout_s: float,
    ) -> ProviderReply:
        system = "\\n".join(m.content for m in messages if m.role == "system")
        history = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in {"user", "assistant"}
        ]
        tool_defs = [
            {
                "name": item.name,
                "description": item.description,
                "input_schema": item.parameters,
            }
            for item in tools
        ]
        try:
            response = await asyncio.wait_for(
                self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=history,
                    tools=tool_defs or None,
                ),
                timeout=timeout_s,
            )
        except Exception as exc:
            _raise_vendor_error(self.name, exc)
            raise
        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for block in response.content:
            if getattr(block, "type", "") == "text":
                text_parts.append(block.text)
            elif getattr(block, "type", "") == "tool_use":
                calls.append(ToolCall(block.id, block.name, dict(block.input)))
        usage = getattr(response, "usage", None)
        return ProviderReply(
            "".join(text_parts),
            tuple(calls),
            Usage(int(usage.input_tokens), int(usage.output_tokens)) if usage else None,
            str(getattr(response, "stop_reason", "stop")),
        )


def _raise_vendor_error(provider: str, exc: Exception) -> None:
    name = type(exc).__name__
    message = str(exc).lower()
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", {}) or {}
    retry_after = headers.get("retry-after") if hasattr(headers, "get") else None
    try:
        retry = float(retry_after) if retry_after is not None else 0.0
    except (TypeError, ValueError):
        retry = 0.0
    if "authentication" in name.lower() or "permission" in name.lower():
        raise AuthError(provider, "authentication failed") from exc
    if "ratelimit" in name.lower() or "rate limit" in message:
        if any(word in message for word in ("credit balance", "billing", "insufficient_quota")):
            raise QuotaExhausted(provider) from exc
        raise RateLimited(provider, retry) from exc
    if "quota" in message or "credit balance" in message or "billing" in message:
        raise QuotaExhausted(provider) from exc
    if any(word in name.lower() for word in ("connection", "timeout", "apierror")):
        raise ProviderUnavailable(provider, "provider unavailable") from exc
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and status >= 500:
        raise ProviderUnavailable(provider, "provider server error") from exc
    raise ProviderUnavailable(provider, f"provider request failed ({name})") from exc
