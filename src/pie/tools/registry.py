from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
import uuid
from collections import deque
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from pie.events import EventBus
from pie.safety.audit import AuditLog, redact
from pie.safety.paths_guard import guard_paths
from pie.safety.permissions import PermissionDecision, PermissionGate, Tier
from pie.tools.base import Tool, ToolContext, ToolResult, ToolSpec, fail

_LOG = logging.getLogger(__name__)


class ToolRegistry:
    """Single execution boundary for registered tools."""

    def __init__(
        self,
        config: Any,
        bus: EventBus,
        permission_gate: PermissionGate,
        audit: AuditLog,
        *,
        clock: Any = time.monotonic,
    ) -> None:
        self.config = config
        self.bus = bus
        self.permission_gate = permission_gate
        self.audit = audit
        self.clock = clock
        self._tools: dict[str, Tool] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._calls: deque[float] = deque()

    def register(self, tool: Tool) -> None:
        name = tool.spec.name
        if name in self._tools:
            raise ValueError(f"tool already registered: {name}")
        self._tools[name] = tool
        self._locks[name] = asyncio.Lock()

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list(self) -> list[ToolSpec]:
        return [self._tools[name].spec for name in sorted(self._tools)]

    def specs_for_model(self) -> list[ToolSpec]:
        def public_schema(value: Any) -> Any:
            if isinstance(value, dict):
                return {
                    key: public_schema(item)
                    for key, item in value.items()
                    if not (isinstance(key, str) and key.startswith("x-"))
                }
            if isinstance(value, list):
                return [public_schema(item) for item in value]
            return value

        return [
            replace(spec, parameters=public_schema(spec.parameters))
            for spec in self.list()
            if spec.tier is not Tier.BLOCKED and sys.platform in spec.platforms
        ]

    def _setting(self, section: str, key: str, default: Any) -> Any:
        return getattr(getattr(self.config, section, None), key, default)

    def _publish(self, topic: str, payload: dict[str, Any], call_id: str) -> None:
        self.bus.publish(topic, payload, source="tool_registry", correlation_id=call_id)

    def _audit(
        self,
        *,
        call_id: str,
        correlation_id: str | None,
        source: str,
        tool: str,
        args: dict[str, Any],
        tier: Tier,
        decision: str,
        by: str | None,
        ok: bool,
        error: str | None,
        started: float,
        provider: str | None,
    ) -> None:
        self.audit.write(
            {
                "ts": time.time(),
                "call_id": call_id,
                "correlation_id": correlation_id,
                "source": source,
                "tool": tool,
                "args": args,
                "tier": tier.name,
                "decision": decision,
                "by": by,
                "ok": ok,
                "error": error,
                "duration_s": max(0.0, self.clock() - started),
                "provider": provider,
            }
        )

    async def execute(
        self,
        name: str,
        args: Mapping[str, Any],
        *,
        source: str,
        correlation_id: str | None = None,
        pre_approved_by: str | None = None,
        provider: str | None = None,
        dry_run: bool | None = None,
    ) -> ToolResult:
        call_id = uuid.uuid4().hex
        started = self.clock()
        safe_args = dict(args)
        spec_tool = self._tools.get(name)
        if spec_tool is None:
            result = fail("unknown tool")
            self._audit(
                call_id=call_id,
                correlation_id=correlation_id,
                source=source,
                tool=name,
                args=safe_args,
                tier=Tier.READ,
                decision="denied",
                by=None,
                ok=False,
                error=result.error,
                started=started,
                provider=provider,
            )
            return result

        spec = spec_tool.spec
        tier = spec.tier
        if name in self._setting("tools", "disabled", []):
            result = fail("tool is disabled")
            self._audit(
                call_id=call_id,
                correlation_id=correlation_id,
                source=source,
                tool=name,
                args=safe_args,
                tier=tier,
                decision="denied",
                by=None,
                ok=False,
                error=result.error,
                started=started,
                provider=provider,
            )
            return result
        if sys.platform not in spec.platforms:
            result = fail("tool is not supported on this platform")
            self._audit(
                call_id=call_id,
                correlation_id=correlation_id,
                source=source,
                tool=name,
                args=safe_args,
                tier=tier,
                decision="denied",
                by=None,
                ok=False,
                error=result.error,
                started=started,
                provider=provider,
            )
            return result

        try:
            Draft202012Validator.check_schema(spec.parameters)
            errors = sorted(
                Draft202012Validator(spec.parameters).iter_errors(safe_args),
                key=lambda item: (tuple(str(part) for part in item.absolute_path), item.message),
            )
            if errors:
                location = ".".join(str(part) for part in errors[0].absolute_path) or "arguments"
                raise ValueError(f"{location}: {errors[0].message}")
            workspace_root = Path(
                str(self._setting("safety", "sandbox_dir", "~/PieWorkspace"))
            ).expanduser()
            for key, property_schema in spec.parameters.get("properties", {}).items():
                raw_path = safe_args.get(key)
                if (
                    isinstance(property_schema, dict)
                    and property_schema.get("x-path") is True
                    and isinstance(raw_path, str)
                    and not raw_path.startswith("~")
                    and not Path(raw_path).is_absolute()
                ):
                    safe_args[key] = str(workspace_root / raw_path)
            path_tier = guard_paths(
                safe_args,
                spec.parameters,
                allowed_folders=self._setting(
                    "safety",
                    "allowed_folders",
                    ("~/Desktop", "~/Documents", "~/Downloads", "~/PieWorkspace"),
                ),
                audit_path=self._setting("safety", "audit_path", "~/.pie/logs/audit.jsonl"),
            )
            tier = max(tier, path_tier)
            for key, property_schema in spec.parameters.get("properties", {}).items():
                if not isinstance(property_schema, dict) or not isinstance(safe_args.get(key), str):
                    continue
                candidate = Path(str(safe_args[key])).expanduser()
                if property_schema.get("x-confirm-if-exists") is True and candidate.exists():
                    tier = max(tier, Tier.CONFIRM)
                if property_schema.get("x-confirm-outside-sandbox") is True:
                    sandbox = (
                        Path(str(self._setting("safety", "sandbox_dir", "~/PieWorkspace")))
                        .expanduser()
                        .resolve()
                    )
                    resolved = candidate.resolve()
                    try:
                        resolved.relative_to(sandbox)
                    except ValueError:
                        tier = max(tier, Tier.CONFIRM)
        except (ValueError, TypeError, SchemaError) as exc:
            result = fail(str(exc))
            self._audit(
                call_id=call_id,
                correlation_id=correlation_id,
                source=source,
                tool=name,
                args=safe_args,
                tier=tier,
                decision="denied",
                by=None,
                ok=False,
                error=result.error,
                started=started,
                provider=provider,
            )
            return result

        now = self.clock()
        while self._calls and now - self._calls[0] >= 10.0:
            self._calls.popleft()
        max_calls = int(self._setting("safety", "max_calls_per_10s", 10))
        if len(self._calls) >= max_calls:
            result = fail("rate limited")
            self._audit(
                call_id=call_id,
                correlation_id=correlation_id,
                source=source,
                tool=name,
                args=safe_args,
                tier=tier,
                decision="denied",
                by=None,
                ok=False,
                error=result.error,
                started=started,
                provider=provider,
            )
            return result
        self._calls.append(now)

        if not (
            source == "rule" and name == "mac.delete_selected" and pre_approved_by == "voice_phrase"
        ):
            pre_approved_by = None
        redacted_args = redact(safe_args, tool=name)
        self._publish(
            "tool.requested",
            {"call_id": call_id, "tool": name, "args": redacted_args, "tier": tier.name},
            call_id,
        )
        is_dry_run = bool(self._setting("tools", "dry_run", False) if dry_run is None else dry_run)
        prompt_builder = getattr(spec_tool, "confirmation_prompt", None)
        cleanup_builder = getattr(spec_tool, "clear_confirmation", None)

        def clear_confirmation_state() -> None:
            if callable(cleanup_builder):
                cleanup_builder(call_id)

        custom_prompt = None
        if not is_dry_run and tier is Tier.CONFIRM and callable(prompt_builder):
            custom_prompt = await asyncio.to_thread(prompt_builder, redacted_args, call_id)
        prompt = custom_prompt or (
            f"Allow {name}? {spec.description} Arguments: "
            f"{json.dumps(redacted_args, ensure_ascii=False, default=str)[:1000]}"
        )
        try:
            if tier is Tier.BLOCKED:
                decision = PermissionDecision(False, "blocked")
            elif is_dry_run:
                decision = PermissionDecision(True, "dry_run")
            else:
                decision = await self.permission_gate.request(
                    call_id=call_id,
                    tool=name,
                    args=safe_args,
                    tier=tier,
                    prompt=prompt,
                    timeout_s=float(self._setting("safety", "confirm_timeout_s", 20)),
                    pre_approved_by=pre_approved_by,
                )
        except asyncio.CancelledError:
            clear_confirmation_state()
            self._publish("tool.denied", {"call_id": call_id, "reason": "cancelled"}, call_id)
            self._publish(
                "tool.finished",
                {
                    "call_id": call_id,
                    "ok": False,
                    "summary": "cancelled",
                    "duration_s": self.clock() - started,
                },
                call_id,
            )
            self._audit(
                call_id=call_id,
                correlation_id=correlation_id,
                source=source,
                tool=name,
                args=safe_args,
                tier=tier,
                decision="denied",
                by="cancelled",
                ok=False,
                error="cancelled",
                started=started,
                provider=provider,
            )
            raise
        if not decision.allow:
            clear_confirmation_state()
            self._publish("tool.denied", {"call_id": call_id, "reason": decision.by}, call_id)
            self._publish(
                "tool.finished",
                {"call_id": call_id, "ok": False, "summary": "denied", "duration_s": 0.0},
                call_id,
            )
            result = fail("permission denied")
            self._audit(
                call_id=call_id,
                correlation_id=correlation_id,
                source=source,
                tool=name,
                args=safe_args,
                tier=tier,
                decision="denied",
                by=decision.by,
                ok=False,
                error=result.error,
                started=started,
                provider=provider,
            )
            return result

        self._publish("tool.approved", {"call_id": call_id, "by": decision.by}, call_id)
        self._publish("tool.started", {"call_id": call_id}, call_id)
        if is_dry_run:
            clear_confirmation_state()
            result = ToolResult(
                True,
                output={
                    "dry_run": True,
                    "tool": name,
                    "args": redacted_args,
                },
            )
            duration = max(0.0, self.clock() - started)
            self._publish(
                "tool.finished",
                {
                    "call_id": call_id,
                    "ok": True,
                    "summary": "dry run; no execution performed",
                    "duration_s": duration,
                },
                call_id,
            )
            self._audit(
                call_id=call_id,
                correlation_id=correlation_id,
                source=source,
                tool=name,
                args=safe_args,
                tier=tier,
                decision="dry_run",
                by="dry_run",
                ok=True,
                error=None,
                started=started,
                provider=provider,
            )
            return result
        workspace = Path(str(self._setting("safety", "sandbox_dir", "~/PieWorkspace"))).expanduser()
        ctx = ToolContext(
            config=self.config,
            bus=self.bus,
            cancel=asyncio.Event(),
            call_id=call_id,
            workdir=workspace,
            dry_run=is_dry_run,
        )
        task: asyncio.Task[ToolResult] | None = None
        try:
            async with self._locks[name]:
                task = asyncio.create_task(spec_tool.run(safe_args, ctx))
                try:
                    result = await asyncio.wait_for(asyncio.shield(task), timeout=spec.timeout_s)
                    if not isinstance(result, ToolResult):
                        result = fail("tool returned an invalid result")
                except TimeoutError:
                    ctx.cancel.set()
                    try:
                        await asyncio.wait_for(task, timeout=1.0)
                    except asyncio.CancelledError:
                        if not task.done():
                            task.cancel()
                    except Exception:
                        if not task.done():
                            task.cancel()
                    result = fail("timeout")
        except asyncio.CancelledError:
            clear_confirmation_state()
            ctx.cancel.set()
            if task is not None and not task.done():
                task.cancel()
            result = fail("cancelled")
            self._audit(
                call_id=call_id,
                correlation_id=correlation_id,
                source=source,
                tool=name,
                args=safe_args,
                tier=tier,
                decision="approved",
                by=decision.by,
                ok=False,
                error=result.error,
                started=started,
                provider=provider,
            )
            self._publish(
                "tool.finished",
                {
                    "call_id": call_id,
                    "ok": False,
                    "summary": "cancelled",
                    "duration_s": self.clock() - started,
                },
                call_id,
            )
            raise
        except Exception as exc:
            clear_confirmation_state()
            result = fail(f"tool raised {type(exc).__name__}")

        clear_confirmation_state()
        limit = int(self._setting("tools", "result_max_chars", 20000))
        if isinstance(result.output, str) and len(result.output) > limit:
            result.output = result.output[: max(0, limit - 11)] + "[truncated]"
        duration = max(0.0, self.clock() - started)
        summary = (
            f"text result ({len(result.output)} characters)"
            if isinstance(result.output, str)
            else "failed"
            if result.error
            else "completed"
        )
        self._publish(
            "tool.finished",
            {
                "call_id": call_id,
                "ok": result.ok,
                "summary": str(summary)[:500],
                "duration_s": duration,
            },
            call_id,
        )
        self._audit(
            call_id=call_id,
            correlation_id=correlation_id,
            source=source,
            tool=name,
            args=safe_args,
            tier=tier,
            decision="approved",
            by=decision.by,
            ok=result.ok,
            error=result.error,
            started=started,
            provider=provider,
        )
        return result


__all__ = ["ToolRegistry"]
