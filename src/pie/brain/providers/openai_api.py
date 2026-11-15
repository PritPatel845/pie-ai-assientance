from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from typing import Any

from pie.brain.keys import get_api_key
from pie.brain.providers.anthropic_api import _raise_vendor_error
from pie.brain.types import (
    AuthError,
    Message,
    ProviderReply,
    ToolCall,
    ToolSpec,
    Usage,
)


class OpenAIProvider:
    name = "openai"
    kind = "cloud"

    def __init__(self, model: str, *, client: Any | None = None) -> None:
        self.model = model
        if client is None:
            from openai import AsyncOpenAI

            key = get_api_key("openai")
            if not key:
                raise AuthError(self.name, "API key not configured")
            client = AsyncOpenAI(api_key=key)
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
        rows: list[dict[str, Any]] = []
        for message in messages:
            row: dict[str, Any] = {"role": message.role, "content": message.content}
            if message.tool_call_id:
                row["tool_call_id"] = message.tool_call_id
            if message.tool_calls:
                row["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.args),
                        },
                    }
                    for call in message.tool_calls
                ]
            rows.append(row)
        tool_defs = [
            {
                "type": "function",
                "function": {
                    "name": item.name,
                    "description": item.description,
                    "parameters": item.parameters,
                },
            }
            for item in tools
        ]
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=rows,
                    max_tokens=max_tokens,
                    tools=tool_defs or None,
                ),
                timeout=timeout_s,
            )
        except Exception as exc:
            _raise_vendor_error(self.name, exc)
            raise
        choice = response.choices[0]
        message = choice.message
        calls: list[ToolCall] = []
        for call in message.tool_calls or []:
            calls.append(
                ToolCall(
                    call.id,
                    call.function.name,
                    json.loads(call.function.arguments or "{}"),
                )
            )
        usage = getattr(response, "usage", None)
        return ProviderReply(
            message.content or "",
            tuple(calls),
            Usage(int(usage.prompt_tokens), int(usage.completion_tokens)) if usage else None,
            str(choice.finish_reason or "stop"),
        )
