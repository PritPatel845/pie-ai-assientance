from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from pie.brain.providers.local import LocalProvider
from pie.brain.types import Message


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeHttpClient:
    def __init__(
        self,
        *,
        ollama_models: list[dict[str, Any]] | None = None,
        mlx_models: list[dict[str, Any]] | None = None,
    ) -> None:
        self.ollama_models = ollama_models or []
        self.mlx_models = mlx_models or []
        self.post_payload: dict[str, Any] | None = None

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        del kwargs
        if url.endswith("/api/tags"):
            return FakeResponse({"models": self.ollama_models})
        return FakeResponse({"data": self.mlx_models})

    async def post(self, url: str, *, json: dict[str, Any], **kwargs: Any) -> FakeResponse:
        del url, kwargs
        self.post_payload = json
        return FakeResponse(
            {"choices": [{"message": {"content": "local answer"}, "finish_reason": "stop"}]}
        )


def test_ollama_selects_largest_model_within_disk_budget() -> None:
    async def scenario() -> None:
        client = FakeHttpClient(
            ollama_models=[
                {"name": "small", "size": 2 * 1024**3},
                {"name": "too-large", "size": 8 * 1024**3},
            ]
        )
        provider = LocalProvider(backend="ollama", max_ram_gb=6.0, client=client)  # type: ignore[arg-type]

        assert await provider.healthcheck()
        assert provider._choose_model() == "small"

    asyncio.run(scenario())


def test_mlx_uses_cached_model_disk_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        model_dir = tmp_path / "models--org--tiny"
        snapshot = model_dir / "snapshots" / "revision"
        snapshot.mkdir(parents=True)
        (snapshot / "weights.bin").write_bytes(b"x" * 256)
        client = FakeHttpClient(mlx_models=[{"id": "org/tiny"}])
        monkeypatch.setenv("PIE_MLX_BASE_URL", "http://127.0.0.1:1234/v1")
        provider = LocalProvider(
            backend="mlx",
            max_ram_gb=1.0,
            client=client,  # type: ignore[arg-type]
            model_cache_dir=tmp_path,
        )

        assert await provider.healthcheck()
        assert provider._models == [("org/tiny", 256)]
        assert provider._choose_model() == "org/tiny"

    asyncio.run(scenario())


def test_configured_model_over_budget_is_not_selected() -> None:
    async def scenario() -> None:
        client = FakeHttpClient(ollama_models=[{"name": "large", "size": 8 * 1024**3}])
        provider = LocalProvider(
            backend="ollama",
            model="large",
            max_ram_gb=6.0,
            client=client,  # type: ignore[arg-type]
        )

        assert not await provider.healthcheck()
        assert provider._choose_model() == ""

    asyncio.run(scenario())


def test_local_completion_checks_memory_and_sends_keep_alive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        import pie.brain.providers.local as local_module

        client = FakeHttpClient(ollama_models=[{"name": "small", "size": 1 * 1024**3}])
        provider = LocalProvider(backend="ollama", client=client)  # type: ignore[arg-type]
        monkeypatch.setattr(
            local_module.psutil,
            "virtual_memory",
            lambda: SimpleNamespace(available=4 * 1024**3),
        )

        reply = await provider.complete(
            [Message("user", "hello")],
            [],
            max_tokens=32,
            timeout_s=1.0,
        )

        assert reply.text == "local answer"
        assert client.post_payload is not None
        assert client.post_payload["keep_alive"] == "2m"
        assert client.post_payload["model"] == "small"

    asyncio.run(scenario())
