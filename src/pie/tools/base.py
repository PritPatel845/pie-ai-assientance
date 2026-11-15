from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from pie.events import EventBus
from pie.safety.permissions import Tier


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    tier: Tier
    timeout_s: float = 30.0
    platforms: tuple[str, ...] = ("darwin",)

    def __post_init__(self) -> None:
        parts = self.name.split(".")
        valid_parts = len(parts) == 2 and all(
            part and part.replace("_", "").isalnum() and part.islower()
            for part in parts
        )
        if not valid_parts:
            raise ValueError("tool name must use lowercase domain.verb characters")
        if not isinstance(self.parameters, dict) or self.parameters.get("type") != "object":
            raise ValueError("tool parameters must be a JSON Schema object")
        if self.parameters.get("additionalProperties") is not False:
            raise ValueError("tool schema must set additionalProperties=false")
        if self.timeout_s <= 0:
            raise ValueError("tool timeout must be positive")


@dataclass(slots=True)
class ToolResult:
    ok: bool
    output: Any = None
    error: str | None = None
    artifacts: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ToolContext:
    config: Any
    bus: EventBus
    cancel: asyncio.Event
    call_id: str
    workdir: Path
    dry_run: bool = False


class Tool(Protocol):
    spec: ToolSpec

    async def run(self, args: Mapping[str, Any], ctx: ToolContext) -> ToolResult: ...


@dataclass(slots=True)
class FunctionTool:
    spec: ToolSpec
    function: Callable[[Mapping[str, Any], ToolContext], Awaitable[ToolResult]]
    confirmation_prompt_builder: Callable[[Mapping[str, Any], str], str] | None = None

    def confirmation_prompt(self, args: Mapping[str, Any], call_id: str) -> str | None:
        if self.confirmation_prompt_builder is None:
            return None
        return self.confirmation_prompt_builder(args, call_id)

    async def run(self, args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        return await self.function(args, ctx)


def ok(output: Any = None, *, artifacts: list[str] | None = None) -> ToolResult:
    return ToolResult(True, output=output, artifacts=[] if artifacts is None else artifacts)


def fail(error: str, *, output: Any = None) -> ToolResult:
    return ToolResult(False, output=output, error=error)
