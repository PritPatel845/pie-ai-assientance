from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pie.events import EventBus
from pie.safety.audit import AuditLog
from pie.safety.permissions import PermissionGate, Tier
from pie.tools.base import FunctionTool, ToolContext, ToolResult, ToolSpec, ok
from pie.tools.registry import ToolRegistry


def _registry(tmp_path: Path, *, max_calls: int = 20, result_limit: int = 100) -> tuple[
    ToolRegistry, PermissionGate, EventBus
]:
    bus = EventBus(asyncio.get_running_loop())
    gate = PermissionGate(bus, timeout_s=0.05)
    gate.start()
    config = SimpleNamespace(
        safety=SimpleNamespace(
            allowed_folders=(str(tmp_path),),
            audit_path=str(tmp_path / "audit.jsonl"),
            sandbox_dir=str(tmp_path / "sandbox"),
            max_calls_per_10s=max_calls,
            confirm_timeout_s=0.05,
        ),
        tools=SimpleNamespace(
            disabled=(),
            dry_run=False,
            result_max_chars=result_limit,
        ),
    )
    audit = AuditLog(tmp_path / "audit.jsonl")
    return ToolRegistry(config, bus, gate, audit), gate, bus


def _tool(
    name: str = "test.echo",
    *,
    tier: Tier = Tier.READ,
    function: Any = None,
    schema: dict[str, Any] | None = None,
    timeout_s: float = 0.2,
) -> FunctionTool:
    async def default(args: Any, ctx: ToolContext) -> ToolResult:
        del ctx
        return ok(dict(args))

    return FunctionTool(
        ToolSpec(
            name,
            "A deterministic test tool.",
            schema
            or {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "additionalProperties": False,
            },
            tier,
            timeout_s=timeout_s,
            platforms=(sys.platform,),
        ),
        function or default,
    )


def test_registry_executes_validated_tool_and_audits(tmp_path: Path) -> None:
    async def scenario() -> None:
        registry, gate, _ = _registry(tmp_path)
        registry.register(_tool())
        result = await registry.execute("test.echo", {"value": "hello"}, source="text")
        assert result.ok
        assert result.output == {"value": "hello"}
        record = json.loads((tmp_path / "audit.jsonl").read_text(encoding="utf-8"))
        assert record["tool"] == "test.echo"
        assert record["decision"] == "approved"
        gate.stop()

    asyncio.run(scenario())


def test_registry_rejects_invalid_arguments_before_execution(tmp_path: Path) -> None:
    async def scenario() -> None:
        called = False

        async def function(args: Any, ctx: ToolContext) -> ToolResult:
            nonlocal called
            called = True
            return ok(dict(args))

        registry, gate, _ = _registry(tmp_path)
        registry.register(_tool(function=function))
        result = await registry.execute(
            "test.echo", {"value": "hello", "extra": True}, source="agent"
        )
        assert not result.ok
        assert not called
        gate.stop()

    asyncio.run(scenario())


def test_registry_rejects_unknown_and_disabled_tools(tmp_path: Path) -> None:
    async def scenario() -> None:
        registry, gate, _ = _registry(tmp_path)
        unknown = await registry.execute("test.missing", {}, source="agent")
        assert not unknown.ok
        registry.config.tools.disabled = ("test.echo",)
        registry.register(_tool())
        disabled = await registry.execute("test.echo", {"value": "x"}, source="agent")
        assert not disabled.ok
        gate.stop()

    asyncio.run(scenario())


def test_blocked_tools_are_not_exposed_or_executed(tmp_path: Path) -> None:
    async def scenario() -> None:
        registry, gate, _ = _registry(tmp_path)
        registry.register(_tool("test.blocked", tier=Tier.BLOCKED))
        assert registry.specs_for_model() == []
        result = await registry.execute("test.blocked", {"value": "x"}, source="agent")
        assert not result.ok
        assert result.error == "permission denied"
        gate.stop()

    asyncio.run(scenario())


def test_dry_run_never_calls_tool_or_requests_confirmation(tmp_path: Path) -> None:
    async def scenario() -> None:
        called = False

        async def function(args: Any, ctx: ToolContext) -> ToolResult:
            nonlocal called
            called = True
            return ok(dict(args))

        registry, gate, _ = _registry(tmp_path)
        registry.register(_tool(tier=Tier.CONFIRM, function=function))
        result = await registry.execute(
            "test.echo", {"value": "hello"}, source="text", dry_run=True
        )
        assert result.ok
        assert result.output["dry_run"] is True
        assert not called
        gate.stop()

    asyncio.run(scenario())


def test_confirm_tier_requires_addressed_voice_approval(tmp_path: Path) -> None:
    async def scenario() -> None:
        registry, gate, bus = _registry(tmp_path)
        registry.register(_tool(tier=Tier.CONFIRM))
        task = asyncio.create_task(
            registry.execute("test.echo", {"value": "hello"}, source="agent")
        )
        await asyncio.sleep(0.01)
        bus.publish(
            "input.voice.transcript",
            {"final": True, "addressed": True, "text": "yes"},
            source="voice",
        )
        result = await task
        assert result.ok
        gate.stop()

    asyncio.run(scenario())


def test_agent_cannot_self_approve_confirm_tier_tool(tmp_path: Path) -> None:
    async def scenario() -> None:
        registry, gate, bus = _registry(tmp_path)
        registry.register(_tool(tier=Tier.CONFIRM))
        task = asyncio.create_task(
            registry.execute(
                "test.echo",
                {"value": "hello"},
                source="agent",
                pre_approved_by="voice_phrase",
            )
        )
        await asyncio.sleep(0.01)
        assert not task.done()
        bus.publish(
            "input.voice.transcript",
            {"final": True, "addressed": True, "text": "yes"},
            source="voice",
        )
        assert (await task).ok
        gate.stop()

    asyncio.run(scenario())


def test_explicit_rule_preapproval_is_accepted(tmp_path: Path) -> None:
    async def scenario() -> None:
        registry, gate, _ = _registry(tmp_path)
        registry.register(_tool(tier=Tier.CONFIRM))
        result = await registry.execute(
            "test.echo",
            {"value": "hello"},
            source="rule",
            pre_approved_by="voice_phrase",
        )
        assert result.ok
        gate.stop()

    asyncio.run(scenario())


def test_tool_timeout_returns_failure_and_audits(tmp_path: Path) -> None:
    async def scenario() -> None:
        async def slow(args: Any, ctx: ToolContext) -> ToolResult:
            del args
            await asyncio.sleep(0.1)
            return ok("late")

        registry, gate, _ = _registry(tmp_path)
        registry.register(_tool(function=slow, timeout_s=0.01))
        result = await registry.execute("test.echo", {"value": "x"}, source="agent")
        assert not result.ok and result.error == "timeout"
        gate.stop()

    asyncio.run(scenario())


def test_tool_exception_is_contained_and_audited(tmp_path: Path) -> None:
    async def scenario() -> None:
        async def broken(args: Any, ctx: ToolContext) -> ToolResult:
            del args, ctx
            raise RuntimeError("safe test failure")

        registry, gate, _ = _registry(tmp_path)
        registry.register(_tool(function=broken))
        result = await registry.execute("test.echo", {"value": "x"}, source="agent")
        assert not result.ok
        assert "RuntimeError" in str(result.error)
        gate.stop()

    asyncio.run(scenario())


def test_string_result_is_truncated(tmp_path: Path) -> None:
    async def scenario() -> None:
        async def long_result(args: Any, ctx: ToolContext) -> ToolResult:
            del args, ctx
            return ok("x" * 50)

        registry, gate, _ = _registry(tmp_path, result_limit=20)
        registry.register(_tool(function=long_result))
        result = await registry.execute("test.echo", {"value": "x"}, source="agent")
        assert result.output == "xxxxxxxxx[truncated]"
        gate.stop()

    asyncio.run(scenario())


def test_rate_limit_blocks_calls_over_configured_window(tmp_path: Path) -> None:
    async def scenario() -> None:
        registry, gate, _ = _registry(tmp_path, max_calls=1)
        registry.register(_tool())
        first = await registry.execute("test.echo", {"value": "x"}, source="agent")
        second = await registry.execute("test.echo", {"value": "x"}, source="agent")
        assert first.ok
        assert not second.ok and second.error == "rate limited"
        gate.stop()

    asyncio.run(scenario())


def test_path_outside_sandbox_requires_confirmation(tmp_path: Path) -> None:
    async def scenario() -> None:
        registry, gate, bus = _registry(tmp_path)
        schema = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "x-path": True,
                    "x-confirm-outside-sandbox": True,
                }
            },
            "required": ["path"],
            "additionalProperties": False,
        }
        registry.register(_tool("fs.test", tier=Tier.READ, schema=schema))
        task = asyncio.create_task(
            registry.execute(
                "fs.test", {"path": str(tmp_path / "outside.txt")}, source="agent"
            )
        )
        await asyncio.sleep(0.01)
        bus.publish(
            "input.voice.transcript",
            {"final": True, "addressed": True, "text": "yes"},
            source="voice",
        )
        result = await task
        assert result.ok
        gate.stop()

    asyncio.run(scenario())


def test_same_tool_calls_are_serialized(tmp_path: Path) -> None:
    async def scenario() -> None:
        active = 0
        maximum = 0

        async def measured(args: Any, ctx: ToolContext) -> ToolResult:
            nonlocal active, maximum
            del args
            active += 1
            maximum = max(maximum, active)
            await asyncio.sleep(0.02)
            active -= 1
            return ok("done")

        registry, gate, _ = _registry(tmp_path)
        registry.register(_tool(function=measured))
        results = await asyncio.gather(
            registry.execute("test.echo", {"value": "1"}, source="agent"),
            registry.execute("test.echo", {"value": "2"}, source="agent"),
        )
        assert all(result.ok for result in results)
        assert maximum == 1
        gate.stop()

    asyncio.run(scenario())
