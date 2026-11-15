from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pie.safety.permissions import Tier
from pie.tools.base import FunctionTool, ToolContext, ToolResult, ToolSpec, ok


def build_system_tools(controller: Any) -> list[FunctionTool]:
    async def system_time(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        del args, ctx
        now = datetime.now().astimezone()
        return ok(
            {
                "datetime": now.isoformat(),
                "timezone": str(now.tzinfo),
                "date": now.date().isoformat(),
            }
        )

    async def frontmost_app(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        del args
        if ctx.dry_run:
            return ok({"app": "dry-run"})
        value = await asyncio.to_thread(controller.frontmost_app)
        return ok({"app": value})

    empty_schema = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }
    return [
        FunctionTool(
            ToolSpec(
                "system.time",
                "Get the current local date, time, and timezone.",
                empty_schema,
                Tier.READ,
            ),
            system_time,
        ),
        FunctionTool(
            ToolSpec(
                "mac.frontmost_app",
                (
                    "Identify the frontmost macOS application. "
                    "Do not use to infer hidden windows."
                ),
                empty_schema,
                Tier.READ,
            ),
            frontmost_app,
        ),
    ]
