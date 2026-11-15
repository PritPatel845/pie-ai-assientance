from __future__ import annotations

from datetime import datetime
from typing import Any

from pie.safety.permissions import Tier
from pie.tools.base import FunctionTool, ToolContext, ToolResult, ToolSpec, ok


def build_system_tools(controller: Any) -> list[FunctionTool]:
    async def system_time(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        del args, ctx
        now = datetime.now().astimezone()
        return ok({"datetime": now.isoformat(), "timezone": str(now.tzinfo), "date": now.date().isoformat()})

    async def frontmost_app(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        del args
        if ctx.dry_run:
            return ok({"app": "dry-run"})
        value = await __import__("asyncio").to_thread(controller.frontmost_app)
        return ok({"app": value})

    return [
        FunctionTool(
            ToolSpec("system.time", "Get the current local date, time, and timezone.", {
                "type": "object", "properties": {}, "additionalProperties": False
            }, Tier.READ),
            system_time,
        ),
        FunctionTool(
            ToolSpec("mac.frontmost_app", "Identify the frontmost macOS application. Do not use to infer hidden windows.", {
                "type": "object", "properties": {}, "additionalProperties": False
            }, Tier.READ),
            frontmost_app,
        ),
    ]
