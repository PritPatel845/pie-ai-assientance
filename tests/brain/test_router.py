from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal

from pie.brain.quota import QuotaTracker
from pie.brain.router import BrainRouter
from pie.brain.types import (
    Message,
    ProviderReply,
    QuotaExhausted,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from pie.config import BrainConfig
from pie.events import EventBus


class FakeProvider:
    def __init__(
        self,
        name: str,
        kind: Literal["cloud", "local"],
        *,
        error: Exception | None = None,
        text: str = "answer",
        gate: asyncio.Event | None = None,
    ) -> None:
        self.name = name
        self.kind = kind
        self.error = error
        self.text = text
        self.gate = gate
        self.seen_tools: list[list[ToolSpec]] = []

    async def healthcheck(self) -> bool:
        return True

    async def complete(
        self,
        messages: list[Message] | tuple[Message, ...],
        tools: list[ToolSpec],
        *,
        max_tokens: int,
        timeout_s: float,
    ) -> ProviderReply:
        self.seen_tools.append(tools)
        if self.gate is not None:
            self.gate.set()
            await asyncio.Event().wait()
        if self.error is not None:
            raise self.error
        return ProviderReply(self.text)


async def _rule_executor(_match: object) -> bool:
    return True


async def _tool_runner(_call: ToolCall, _source: str) -> ToolResult:
    return ToolResult(True)


def _router(
    providers: dict[str, FakeProvider],
    tmp_path: Path,
    *,
    config: BrainConfig | None = None,
) -> BrainRouter:
    return BrainRouter(
        config or BrainConfig(anthropic_model="claude-test", openai_model="gpt-test"),
        EventBus(asyncio.get_running_loop()),
        providers,  # type: ignore[arg-type]
        QuotaTracker(tmp_path / "quota.json"),
        _rule_executor,
        lambda: [ToolSpec("dangerous", "not available in Phase 2B", {})],
        _tool_runner,
    )


def test_cloud_quota_falls_through_to_next_cloud_before_local(tmp_path: Path) -> None:
    async def scenario() -> None:
        anthropic = FakeProvider("anthropic", "cloud", error=QuotaExhausted("anthropic"))
        openai = FakeProvider("openai", "cloud", text="from openai")
        local = FakeProvider("local", "local")
        router = _router({"anthropic": anthropic, "openai": openai, "local": local}, tmp_path)

        result = await router.handle("explain gravity", source="test")

        assert result.provider == "openai"
        assert result.text == "from openai"
        assert not anthropic.seen_tools[0]
        assert not openai.seen_tools[0]
        assert not local.seen_tools

    asyncio.run(scenario())


def test_all_cloud_providers_exhausted_switches_to_local(tmp_path: Path) -> None:
    async def scenario() -> None:
        anthropic = FakeProvider("anthropic", "cloud", error=QuotaExhausted("anthropic"))
        openai = FakeProvider("openai", "cloud", error=QuotaExhausted("openai"))
        local = FakeProvider("local", "local", text="offline answer")
        router = _router({"anthropic": anthropic, "openai": openai, "local": local}, tmp_path)

        result = await router.handle("explain gravity", source="test")

        assert result.provider == "local"
        assert result.text == "offline answer"
        assert not local.seen_tools[0]

    asyncio.run(scenario())


def test_explicit_local_skips_cloud(tmp_path: Path) -> None:
    async def scenario() -> None:
        anthropic = FakeProvider("anthropic", "cloud")
        local = FakeProvider("local", "local", text="local answer")
        router = _router({"anthropic": anthropic, "local": local}, tmp_path)

        result = await router.handle("use local explain gravity", source="test")

        assert result.provider == "local"
        assert result.text == "local answer"
        assert not anthropic.seen_tools

    asyncio.run(scenario())


def test_deterministic_rule_skips_all_models(tmp_path: Path) -> None:
    async def scenario() -> None:
        cloud = FakeProvider("anthropic", "cloud")
        router = _router({"anthropic": cloud}, tmp_path)

        result = await router.handle("open Safari", source="test")

        assert result.route == "rule"
        assert result.ok
        assert not cloud.seen_tools

    asyncio.run(scenario())


def test_stop_cancels_active_provider_request(tmp_path: Path) -> None:
    async def scenario() -> None:
        gate = asyncio.Event()
        cloud = FakeProvider("anthropic", "cloud", gate=gate)
        router = _router({"anthropic": cloud}, tmp_path)
        running = asyncio.create_task(router.handle("explain gravity", source="test"))
        await asyncio.wait_for(gate.wait(), timeout=1.0)

        stopped = await router.handle("stop", source="test")
        result = await asyncio.wait_for(running, timeout=1.0)

        assert stopped.text == "Cancelled."
        assert result.text == "Cancelled."

    asyncio.run(scenario())
