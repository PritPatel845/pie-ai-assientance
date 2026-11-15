from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

from pie.brain.keys import get_api_key, set_api_key
from pie.brain.providers import build_providers
from pie.brain.quota import QuotaTracker
from pie.brain.router import BrainRouter
from pie.brain.rules import match_rule
from pie.brain.types import Message, RuleMatch, ToolCall, ToolResult
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


def _quota_status(tracker: QuotaTracker, provider: str) -> str:
    item = tracker.snapshot().get(provider)
    if item is None:
        return "available"
    until = item.get("exhausted_until")
    if isinstance(until, int | float) and not isinstance(until, bool):
        return f"blocked until {until:.0f}" if until > tracker.clock() else "cooldown expired"
    return "available"


async def _status(config: Any) -> int:
    providers = build_providers(config.brain)
    tracker = QuotaTracker(default_cooldown_s=config.brain.default_cooldown_s)
    try:
        names = list(config.brain.cloud_order)
        if config.brain.cli_providers_enabled:
            names.extend(("claude_cli", "codex_cli"))
        names.append("local")
        status: dict[str, dict[str, Any]] = {}
        for name in names:
            provider = providers.get(name)
            configured = (
                bool(config.brain.anthropic_model)
                if name == "anthropic"
                else bool(config.brain.openai_model)
                if name == "openai"
                else name in {"local", "claude_cli", "codex_cli"}
            )
            key_present = bool(get_api_key(name)) if name in {"anthropic", "openai"} else None
            item: dict[str, Any] = {
                "configured": configured,
                "key_present": key_present,
                "quota": _quota_status(tracker, name),
                "health": "not configured",
                "latency_ms": None,
            }
            if name in {"claude_cli", "codex_cli"}:
                item["health"] = "stubbed: unsafe to sandbox"
            elif provider is not None and configured:
                started = perf_counter()
                try:
                    healthy = await provider.healthcheck()
                    item["health"] = "ready" if healthy else "unavailable"
                except Exception:
                    item["health"] = "unavailable"
                item["latency_ms"] = round((perf_counter() - started) * 1000, 2)
                if name == "local":
                    model = getattr(provider, "_choose_model", lambda: "")()
                    models = getattr(provider, "_models", [])
                    size = next((size for model_name, size in models if model_name == model), 0)
                    item["model"] = model or config.brain.local_model or "auto"
                    item["model_size_bytes"] = size or None
            elif provider is None and configured:
                item["health"] = "optional dependency missing or provider unavailable"
            status[name] = item
        print(json.dumps(status, indent=2))
        return 0
    finally:
        await _close_providers(providers)


async def _test_provider(config: Any, name: str) -> int:
    providers = build_providers(config.brain)
    try:
        provider = providers.get(name)
        if provider is None:
            print(f"{name}: not configured or provider dependency unavailable", file=sys.stderr)
            return 1
        if name in {"anthropic", "openai"} and not get_api_key(name):
            print(f"{name}: API key is not present", file=sys.stderr)
            return 1
        if not await provider.healthcheck():
            print(f"{name}: healthcheck failed", file=sys.stderr)
            return 1
        reply = await provider.complete(
            [Message("user", "Reply with the single word OK")],
            [],
            max_tokens=16,
            timeout_s=config.brain.provider_timeout_s,
        )
        if reply.text.strip() != "OK":
            print(f"{name}: unexpected response: {reply.text[:100]!r}", file=sys.stderr)
            return 1
        print(f"{name}: OK")
        return 0
    except Exception as exc:
        print(f"{name}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
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
        print(f"Route: {result.route} | Provider: {result.provider or 'none'}")
        print(result.text)
        if result.error:
            print(result.error, file=sys.stderr)
        return 0 if result.ok else 1
    finally:
        await _close_providers(providers)


def run_quota_command(action: str | None, arguments: list[str], config_path: Path | None) -> int:
    config = load_config(config_path)
    tracker = QuotaTracker(default_cooldown_s=config.brain.default_cooldown_s)
    if action in {None, "show"}:
        print(json.dumps(tracker.snapshot(), indent=2))
        return 0
    if action == "reset":
        provider = arguments[0] if arguments else None
        tracker.reset(None if provider in {None, "all"} else provider)
        print("Quota state reset.")
        return 0
    raise ValueError("usage: pie quota [show|reset <provider|all>]")


def run_brain_command(action: str | None, arguments: list[str], config_path: Path | None) -> int:
    config = load_config(config_path)
    if action == "status":
        return asyncio.run(_status(config))
    if action == "ask":
        if not arguments:
            raise ValueError("usage: pie brain ask <prompt>")
        return asyncio.run(_ask(config, " ".join(arguments)))
    if action == "test":
        if len(arguments) != 1:
            raise ValueError("usage: pie brain test <provider>")
        return asyncio.run(_test_provider(config, arguments[0]))
    if action == "set-key":
        if len(arguments) != 1:
            raise ValueError("usage: pie brain set-key <anthropic|openai>")
        set_api_key(arguments[0])
        print(f"{arguments[0]} key stored in the system Keychain.")
        return 0
    if action == "quota":
        return run_quota_command(arguments[0] if arguments else None, arguments[1:], config_path)
    raise ValueError(
        "usage: pie brain <status|test <provider>|ask <prompt>|set-key <provider>>"
    )
