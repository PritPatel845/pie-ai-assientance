from __future__ import annotations

import json
import os
from collections.abc import Sequence
from typing import Any

import httpx
import psutil

from pie.brain.types import (
    Message, ProviderReply, ProviderUnavailable, ToolCall, ToolSpec, Usage,
)


class LocalProvider:
    name = "local"
    kind = "local"

    def __init__(
        self, *, backend: str = "auto", model: str = "", max_ram_gb: float = 6.0,
        keep_alive: str = "2m", client: httpx.AsyncClient | None = None,
    ) -> None:
        self.backend = backend
        self.model = model
        self.max_ram_bytes = int(max_ram_gb * 1024**3)
        self.keep_alive = keep_alive
        self.client = client or httpx.AsyncClient(timeout=45.0)
        self.base_url = ""
        self._models: list[tuple[str, int]] = []

    async def _probe_ollama(self) -> bool:
        try:
            response = await self.client.get("http://127.0.0.1:11434/api/tags", timeout=2.0)
            response.raise_for_status()
            payload = response.json()
            self._models = [
                (str(item.get("name", "")), int(item.get("size", 0)))
                for item in payload.get("models", [])
            ]
            self.base_url = "http://127.0.0.1:11434/v1"
            return True
        except (httpx.HTTPError, ValueError, TypeError):
            return False

    async def _probe_mlx(self) -> bool:
        endpoint = os.environ.get("PIE_MLX_BASE_URL", "").rstrip("/")
        if not endpoint:
            return False
        try:
            response = await self.client.get(f"{endpoint}/models", timeout=2.0)
            response.raise_for_status()
            payload = response.json()
            self._models = [(str(item.get("id", "")), 0) for item in payload.get("data", [])]
            self.base_url = endpoint
            return bool(self._models)
        except (httpx.HTTPError, ValueError, TypeError):
            return False

    async def healthcheck(self) -> bool:
        if self.backend in {"auto", "ollama"} and await self._probe_ollama():
            return bool(self._choose_model())
        if self.backend in {"auto", "mlx"} and await self._probe_mlx():
            return bool(self._choose_model())
        return False

    def _choose_model(self) -> str:
        if self.model:
            selected = next((name for name, _ in self._models if name == self.model), None)
            if selected is None:
                return ""
            return selected
        eligible = [
            (name, size) for name, size in self._models
            if size <= self.max_ram_bytes and name
        ]
        if not eligible:
            return ""
        return max(eligible, key=lambda item: item[1])[0]

    async def complete(
        self, messages: Sequence[Message], tools: list[ToolSpec], *,
        max_tokens: int, timeout_s: float
    ) -> ProviderReply:
        if not self.base_url and not await self.healthcheck():
            raise ProviderUnavailable(self.name, "local server unavailable; start Ollama")
        model = self._choose_model()
        if not model:
            raise ProviderUnavailable(
                self.name, "no installed local model within configured budget"
            )
        model_size = next((size for name, size in self._models if name == model), 0)
        available = psutil.virtual_memory().available
        if available < model_size + 2 * 1024**3:
            raise ProviderUnavailable(self.name, "not enough free memory")
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": item.role, "content": item.content,
                 **({"tool_call_id": item.tool_call_id} if item.tool_call_id else {})}
                for item in messages
            ],
            "max_tokens": max_tokens,
            "stream": False,
            "keep_alive": self.keep_alive,
        }
        if tools:
            payload["tools"] = [{
                "type": "function",
                "function": {"name": item.name, "description": item.description,
                             "parameters": item.parameters},
            } for item in tools]
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions", json=payload, timeout=timeout_s
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(self.name, "local model request failed") from exc
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        calls: list[ToolCall] = []
        for item in message.get("tool_calls", []):
            function = item.get("function", {})
            try:
                args = json.loads(function.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(str(item.get("id", "")), str(function.get("name", "")), args))
        usage_data = data.get("usage")
        usage = Usage(int(usage_data.get("prompt_tokens", 0)),
                      int(usage_data.get("completion_tokens", 0))) if usage_data else None
        return ProviderReply(str(message.get("content") or ""), tuple(calls), usage,
                             str(choice.get("finish_reason", "stop")))
