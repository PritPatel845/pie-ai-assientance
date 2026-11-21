from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any, cast

from pie.brain.providers import build_providers
from pie.brain.quota import QuotaTracker
from pie.brain.router import BrainRouter
from pie.brain.rules import RuleMatch, rule_preapproved_by, rule_to_tool_call
from pie.brain.types import ToolCall, ToolResult
from pie.core.daemon import Daemon
from pie.events import Event
from pie.inputs.voice.executor import LegacyRuleExecutor
from pie.platform.mac import MacController
from pie.tools.registry import ToolRegistry

_LOG = logging.getLogger(__name__)


async def _no_tool(_call: ToolCall, _source: str) -> ToolResult:
    return ToolResult(False, error="no tools installed")


class BrainModule:
    """Route addressed voice and typed commands through one BrainRouter."""

    name = "brain"

    def __init__(
        self,
        *,
        executor_getter: Callable[[], LegacyRuleExecutor | None] | None = None,
        no_actions: bool = False,
    ) -> None:
        self.router: BrainRouter | None = None
        self._unsubscribers: list[Callable[[], None]] = []
        self._providers: dict[str, Any] = {}
        self._daemon: Daemon | None = None
        self._executor_getter = executor_getter
        self._executor: LegacyRuleExecutor | None = None
        self._no_actions = no_actions

    def start(self, daemon: Daemon) -> None:
        self._daemon = daemon
        if not daemon.config.brain.enabled or daemon.bus is None:
            return
        self._executor = (
            self._executor_getter() if self._executor_getter is not None else None
        ) or LegacyRuleExecutor(MacController(), no_actions=self._no_actions)

        async def execute_rule(match: RuleMatch) -> bool:
            registry = cast(ToolRegistry | None, getattr(daemon, "tool_registry", None))
            if registry is None:
                if self._executor is None:
                    return False
                return self._executor.run(match.action, match.value)
            call = rule_to_tool_call(match)
            result = await registry.execute(
                call.name,
                call.args,
                source="rule",
                correlation_id=call.id,
                pre_approved_by=rule_preapproved_by(match),
            )
            return result.ok

        async def execute_tool(call: ToolCall, source: str) -> ToolResult:
            del source
            registry = getattr(daemon, "tool_registry", None)
            if registry is None:
                return await _no_tool(call, "agent")
            result = await registry.execute(
                call.name,
                call.args,
                source="agent",
                correlation_id=call.id,
            )
            return ToolResult(result.ok, output=result.output, error=result.error)

        self._providers = build_providers(daemon.config.brain)
        registry = getattr(daemon, "tool_registry", None)
        self.router = BrainRouter(
            daemon.config.brain,
            daemon.bus,
            self._providers,
            QuotaTracker(default_cooldown_s=daemon.config.brain.default_cooldown_s),
            execute_rule,
            registry.specs_for_model if registry is not None else lambda: [],
            execute_tool,
        )
        self._unsubscribers = [
            daemon.bus.subscribe(
                "input.voice.transcript", self._on_transcript, name="brain-voice-router"
            ),
            daemon.bus.subscribe(
                "input.text.command", self._on_text_command, name="brain-text-router"
            ),
        ]

    async def _on_transcript(self, event: Event) -> None:
        payload = event.payload
        if not payload.get("final", True) or not payload.get("addressed", False):
            return
        await self._handle_text(event)

    async def _on_text_command(self, event: Event) -> None:
        await self._handle_text(event)

    async def _handle_text(self, event: Event) -> None:
        if self.router is None or self._daemon is None:
            return
        text = event.payload.get("text")
        if not isinstance(text, str) or not text.strip():
            return
        result = await self.router.handle(
            text,
            source=event.source,
            correlation_id=event.correlation_id or event.id,
        )
        if result.ok and result.text.strip():
            _LOG.debug(
                "Brain response ready for speech (route=%s, provider=%s, chars=%d)",
                result.route,
                result.provider or "rule",
                len(result.text),
            )
            self._daemon.bus.publish(
                "tts.say",
                {"text": result.text[:1000], "interrupt": False},
                source="brain",
                correlation_id=event.correlation_id or event.id,
            )
            return

        _LOG.warning(
            "Brain request produced no speakable response (ok=%s, route=%s, provider=%s, error=%s)",
            result.ok,
            result.route,
            result.provider or "rule",
            result.error or "empty response",
        )
        self._daemon.bus.publish(
            "tts.say",
            {
                "text": "I couldn't complete that request. Please try again.",
                "interrupt": False,
            },
            source="brain",
            correlation_id=event.correlation_id or event.id,
        )

    def stop(self) -> None:
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
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
        self._executor = None
        self._daemon = None
