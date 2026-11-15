from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal

from pie.brain.quota import QuotaTracker
from pie.brain.router import BrainRouter
from pie.brain.types import (
    AuthError,
    Message,
    ProviderReply,
    ProviderUnavailable,
    QuotaExhausted,
    RateLimited,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from pie.config import BrainConfig
from pie.events import Event, EventBus


class FakeProvider:
    def __init__(
        self,
        name: str,
        kind: Literal["cloud", "local"],
        *,
        error: Exception | None = None,
        text: str = "answer",
        gate: asyncio.Event | None = None,
        healthy: bool = True,
        errors: list[Exception | None] | None = None,
        delay: float = 0.0,
        replies: list[ProviderReply] | None = None,
    ) -> None:
        self.name = name
        self.kind = kind
        self.error = error
        self.text = text
        self.gate = gate
        self.healthy = healthy
        self.errors = list(errors or [])
        self.delay = delay
        self.replies = list(replies or [])
        self.seen_tools: list[list[ToolSpec]] = []
        self.seen_messages: list[list[Message]] = []

    async def healthcheck(self) -> bool:
        return self.healthy

    async def complete(
        self,
        messages: list[Message] | tuple[Message, ...],
        tools: list[ToolSpec],
        *,
        max_tokens: int,
        timeout_s: float,
    ) -> ProviderReply:
        self.seen_tools.append(tools)
        self.seen_messages.append(list(messages))
        if self.gate is not None:
            self.gate.set()
            await asyncio.Event().wait()
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.errors:
            error = self.errors.pop(0)
            if error is not None:
                raise error
        if self.error is not None:
            raise self.error
        if self.replies:
            return self.replies.pop(0)
        if not self.healthy:
            raise ProviderUnavailable(self.name, "offline")
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
        lambda: [],
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


def test_cloud_success_uses_first_configured_provider(tmp_path: Path) -> None:
    async def scenario() -> None:
        anthropic = FakeProvider("anthropic", "cloud", text="cloud answer")
        openai = FakeProvider("openai", "cloud")
        router = _router({"anthropic": anthropic, "openai": openai}, tmp_path)

        result = await router.handle("explain gravity", source="test")

        assert result.provider == "anthropic"
        assert result.text == "cloud answer"
        assert not openai.seen_tools

    asyncio.run(scenario())


def test_all_cloud_providers_offline_falls_back_without_quota_mark(tmp_path: Path) -> None:
    async def scenario() -> None:
        anthropic = FakeProvider("anthropic", "cloud", healthy=False)
        openai = FakeProvider("openai", "cloud", healthy=False)
        local = FakeProvider("local", "local", text="local answer")
        router = _router({"anthropic": anthropic, "openai": openai, "local": local}, tmp_path)

        result = await router.handle("explain gravity", source="test")

        assert result.provider == "local"
        assert result.ok
        assert router.quota.snapshot() == {}

    asyncio.run(scenario())


def test_short_rate_limit_retries_same_provider_once(tmp_path: Path) -> None:
    async def scenario() -> None:
        anthropic = FakeProvider("anthropic", "cloud", errors=[RateLimited("anthropic", 0.0), None])
        openai = FakeProvider("openai", "cloud")
        router = _router({"anthropic": anthropic, "openai": openai}, tmp_path)

        result = await router.handle("explain gravity", source="test")

        assert result.provider == "anthropic"
        assert len(anthropic.seen_tools) == 2
        assert not openai.seen_tools

    asyncio.run(scenario())


def test_long_rate_limit_moves_to_next_cloud_provider(tmp_path: Path) -> None:
    async def scenario() -> None:
        anthropic = FakeProvider("anthropic", "cloud", errors=[RateLimited("anthropic", 9.0)])
        openai = FakeProvider("openai", "cloud", text="second provider")
        router = _router({"anthropic": anthropic, "openai": openai}, tmp_path)

        result = await router.handle("explain gravity", source="test")

        assert result.provider == "openai"
        assert result.text == "second provider"

    asyncio.run(scenario())


def test_auth_error_warns_and_moves_to_next_provider(tmp_path: Path) -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        warnings: list[Event] = []
        warning_ready = asyncio.Event()

        async def collect(event: Event) -> None:
            warnings.append(event)
            warning_ready.set()

        bus.subscribe("system.warning", collect, name="auth-warning-test")
        anthropic = FakeProvider("anthropic", "cloud", error=AuthError("anthropic"))
        openai = FakeProvider("openai", "cloud", text="authenticated fallback")
        router = BrainRouter(
            BrainConfig(anthropic_model="claude-test", openai_model="gpt-test"),
            bus,
            {"anthropic": anthropic, "openai": openai},  # type: ignore[arg-type]
            QuotaTracker(tmp_path / "quota.json"),
            _rule_executor,
            lambda: [],
            _tool_runner,
        )

        result = await router.handle("explain gravity", source="test")
        await asyncio.wait_for(warning_ready.wait(), timeout=1.0)

        assert result.provider == "openai"
        assert len(warnings) == 1
        assert warnings[0].payload["message"] == "Provider authentication failed"

    asyncio.run(scenario())


def test_local_failure_returns_unavailable_result(tmp_path: Path) -> None:
    async def scenario() -> None:
        local = FakeProvider("local", "local", error=ProviderUnavailable("local", "offline"))
        router = _router({"local": local}, tmp_path, config=BrainConfig())

        result = await router.handle("use local explain gravity", source="test")

        assert not result.ok
        assert result.provider is None
        assert "No AI model is available" in result.text

    asyncio.run(scenario())


def test_total_timeout_is_shared_across_provider_fallbacks(tmp_path: Path) -> None:
    async def scenario() -> None:
        anthropic = FakeProvider("anthropic", "cloud", delay=0.04)
        openai = FakeProvider("openai", "cloud", delay=0.04)
        local = FakeProvider("local", "local")
        config = BrainConfig(
            anthropic_model="claude-test",
            openai_model="gpt-test",
            total_timeout_s=0.05,
            provider_timeout_s=0.03,
        )
        router = _router(
            {"anthropic": anthropic, "openai": openai, "local": local},
            tmp_path,
            config=config,
        )

        result = await router.handle("explain gravity", source="test")

        assert not result.ok
        assert len(anthropic.seen_tools) == 1
        assert len(openai.seen_tools) == 1
        assert not local.seen_tools

    asyncio.run(scenario())
