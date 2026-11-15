from __future__ import annotations

import asyncio
import logging
from typing import Any

from pie.brain.providers import build_providers
from pie.brain.quota import QuotaTracker
from pie.brain.router import BrainRouter
from pie.brain.rules import match_rule
from pie.brain.rules import RuleMatch
from pie.brain.types import ToolCall, ToolResult
from pie.core.daemon import Daemon
from pie.events import Event

_LOG = logging.getLogger(__name__)


async def _no_rule(_match: RuleMatch) -> bool:
    return False


async def _no_tool(_call: ToolCall, _source: str) -> ToolResult:
    return ToolResult(False, error="Tools are disabled until Phase 3A")


class BrainModule:
    """Connect addressed, non-deterministic voice transcripts to the Phase 2B router."""

    name = "brain"

    def __init__(self) -> None:
        self.router: BrainRouter | None = None
        self._unsubscribe: Any | None = None
        self._providers: dict[str, Any] = {}
        self._daemon: Daemon | None = None

    def start(self, daemon: Daemon) -> None:
        self._daemon = daemon
        if not daemon.config.brain.enabled or daemon.bus is None:
            return
        self._providers = build_providers(daemon.config.brain)
        self.router = BrainRouter(
            daemon.config.brain,
            daemon.bus,
            self._providers,
            QuotaTracker(default_cooldown_s=daemon.config.brain.default_cooldown_s),
            _no_rule,
            lambda: [],
            _no_tool,
        )
        self._unsubscribe = daemon.bus.subscribe(
            "input.voice.transcript", self._on_transcript, name="brain-router"
        )

    async def _on_transcript(self, event: Event) -> None:
        if self.router is None or self._daemon is None:
            return
        payload = event.payload
        if not payload.get("final", True) or not payload.get("addressed", False):
            return
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            return
        # The legacy voice executor already handles deterministic commands.
        if match_rule(text) is not None:
            return
        result = await self.router.handle(
            text,
            source=event.source,
            correlation_id=event.correlation_id or event.id,
        )
        if result.ok and result.text and self._daemon.bus is not None:
            self._daemon.bus.publish(
                "tts.say",
                {"text": result.text[:1000], "interrupt": False},
                source="brain",
                correlation_id=event.correlation_id or event.id,
            )

    def stop(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        if self._daemon is not None and self._daemon.loop is not None:
            async def close_providers() -> None:
                for provider in self._providers.values():
                    client = getattr(provider, "client", None)
                    close = getattr(client, "aclose", None) or getattr(client, "close", None)
                    if callable(close):
                        result = close()
                        if asyncio.iscoroutine(result):
                            await result

            if self._daemon.loop.is_running():
                future = asyncio.run_coroutine_threadsafe(close_providers(), self._daemon.loop)
                try:
                    future.result(timeout=2.0)
                except Exception:
                    _LOG.warning("Could not close all brain provider clients", exc_info=True)
        self.router = None
        self._providers.clear()
        self._daemon = None
