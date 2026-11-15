from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from pie.brain.keys import set_api_key
from pie.brain.providers import build_providers
from pie.brain.quota import QuotaTracker
from pie.brain.router import BrainRouter
from pie.brain.rules import RuleMatch, match_rule
from pie.brain.types import ToolCall, ToolResult
from pie.config import load_config
from pie.events import EventBus


async def _no_rule(_match: RuleMatch) -> bool:
    return False


async def _no_tool(_call: ToolCall, _source: str) -> ToolResult:
    return ToolResult(False, error="Tools are not available before Phase 3A")


async def _close_providers(providers: dict[str, Any]) -> None:
    for provider in providers.values():
        client = getattr(provider, "client", None)
        close = getattr(client, "aclose", None) or getattr(client, "close", None)
        if callable(close):
            result = close()
            if asyncio.iscoroutine(result):
                await result


async def _status(config: Any) -> int:
    providers = build_providers(config.brain)
    try:
        status: dict[str, str] = {}
        for name in ("anthropic", "openai", "local"):
            provider = providers.get(name)
            if provider is None:
                status[name] = "not configured or optional dependency missing"
                continue
            try:
                status[name] = "ready" if await provider.healthcheck() else "unavailable"
            except Exception:
                status[name] = "unavailable"
        print(json.dumps(status, indent=2))
        return 0
    finally:
        await _close_providers(providers)


async def _ask(config: Any, prompt: str) -> int:
    if match_rule(prompt) is not None:
        print("This is a deterministic system command; use PIE voice or gesture controls.")
        return 2
    providers = build_providers(config.brain)
    try:
        loop = asyncio.get_running_loop()
        router = BrainRouter(
            config.brain,
            EventBus(loop),
            providers,
            QuotaTracker(default_cooldown_s=config.brain.default_cooldown_s),
            _no_rule,
            lambda: [],
            _no_tool,
        )
        result = await router.handle(prompt, source="cli")
        print(result.text)
        if result.error:
            print(result.error, file=sys.stderr)
        return 0 if result.ok else 1
    finally:
        await _close_providers(providers)


def run_brain_command(action: str | None, arguments: list[str], config_path: Path | None) -> int:
    config = load_config(config_path)
    if action == "status":
        return asyncio.run(_status(config))
    if action == "ask":
        if not arguments:
            raise ValueError("usage: pie brain ask <prompt>")
        return asyncio.run(_ask(config, " ".join(arguments)))
    if action == "test":
        return asyncio.run(_ask(config, "Reply with exactly PIE_BRAIN_OK"))
    if action == "set-key":
        if len(arguments) != 1:
            raise ValueError("usage: pie brain set-key <anthropic|openai>")
        set_api_key(arguments[0])
        print(f"{arguments[0]} key stored in the system Keychain.")
        return 0
    if action == "quota":
        tracker = QuotaTracker(default_cooldown_s=config.brain.default_cooldown_s)
        if not arguments or arguments[0] == "show":
            print(json.dumps(tracker.snapshot(), indent=2))
            return 0
        if arguments[0] == "reset":
            tracker.reset(arguments[1] if len(arguments) > 1 else None)
            print("Quota state reset.")
            return 0
        raise ValueError("usage: pie brain quota [show|reset [provider]]")
    raise ValueError(
        "usage: pie brain <status|test|ask <prompt>|set-key <provider>|quota [show|reset]>"
    )
