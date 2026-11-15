from __future__ import annotations

import asyncio
import re
from pathlib import Path

from pie.brain.quota import QuotaTracker
from pie.brain.router import BrainRouter
from pie.brain.types import ProviderReply, QuotaExhausted
from pie.config import BrainConfig
from pie.events import Event, EventBus


class EventProvider:
    kind = "cloud"

    def __init__(self, name: str, *, error: Exception | None = None) -> None:
        self.name = name
        self.error = error

    async def healthcheck(self) -> bool:
        return True

    async def complete(self, messages, tools, *, max_tokens, timeout_s) -> ProviderReply:
        if self.error is not None:
            raise self.error
        return ProviderReply("ok")


async def _rule(_match: object) -> bool:
    return True


async def _tool(_call, _source):
    raise AssertionError("Phase 2B must not run real tools")


def test_cloud_run_event_order(tmp_path: Path) -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        topics: list[str] = []
        finished = asyncio.Event()

        async def collect(event: Event) -> None:
            topics.append(event.topic)
            if event.topic == "brain.response":
                finished.set()

        for topic in ("intent.resolved", "brain.request", "brain.response"):
            bus.subscribe(topic, collect, name=f"order-{topic}")
        provider = EventProvider("anthropic")
        router = BrainRouter(
            BrainConfig(anthropic_model="configured-model"),
            bus,
            {"anthropic": provider},  # type: ignore[arg-type]
            QuotaTracker(tmp_path / "quota.json"),
            _rule,
            lambda: [],
            _tool,
        )

        await router.handle("explain gravity", source="test")
        await asyncio.wait_for(finished.wait(), timeout=1.0)

        assert topics == ["intent.resolved", "brain.request", "brain.response"]

    asyncio.run(scenario())


def test_quota_fallback_event_order(tmp_path: Path) -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        topics: list[str] = []
        finished = asyncio.Event()

        async def collect(event: Event) -> None:
            topics.append(event.topic)
            if event.topic == "brain.response":
                finished.set()

        expected_topics = (
            "intent.resolved",
            "brain.request",
            "brain.quota",
            "brain.provider.switched",
            "brain.request",
            "brain.response",
        )
        for topic in expected_topics:
            bus.subscribe(topic, collect, name=f"fallback-{topic}")
        providers = {
            "anthropic": EventProvider(
                "anthropic", error=QuotaExhausted("anthropic", reset_at=9999999999.0)
            ),
            "openai": EventProvider("openai"),
        }
        router = BrainRouter(
            BrainConfig(anthropic_model="configured-model", openai_model="configured-model"),
            bus,
            providers,  # type: ignore[arg-type]
            QuotaTracker(tmp_path / "quota.json"),
            _rule,
            lambda: [],
            _tool,
        )

        await router.handle("explain gravity", source="test")
        await asyncio.wait_for(finished.wait(), timeout=1.0)

        assert topics == list(expected_topics)

    asyncio.run(scenario())


def test_source_has_no_hard_coded_model_identifiers() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src" / "pie" / "brain"
    forbidden = re.compile(r"\b(?:gpt-\d|claude-\d|gemini-\d|llama\d)\w*", re.IGNORECASE)
    for path in source_root.rglob("*.py"):
        assert not forbidden.search(path.read_text(encoding="utf-8")), path


def test_cloud_models_are_unset_by_default() -> None:
    config = BrainConfig()
    assert config.anthropic_model == ""
    assert config.openai_model == ""
