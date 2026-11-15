from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from pie.platform.mac import MacController
from pie.safety.permissions import Tier
from pie.tools.base import FunctionTool, ToolContext, ToolResult, ToolSpec, fail, ok


def build_media_tools(controller: MacController) -> list[FunctionTool]:
    async def play(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        del args
        if ctx.dry_run:
            return ok({"would_play": True})
        return ok({"playing": True}) if await asyncio.to_thread(controller.play_media) else fail("media play failed")

    async def pause(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        del args
        if ctx.dry_run:
            return ok({"would_pause": True})
        return ok({"paused": True}) if await asyncio.to_thread(controller.stop_media) else fail("media pause failed")

    schema = {"type": "object", "properties": {}, "additionalProperties": False}
    return [
        FunctionTool(ToolSpec("media.play", "Play or resume the active media session. Do not use to start a specific track.", schema, Tier.REVERSIBLE), play),
        FunctionTool(ToolSpec("media.pause", "Pause the active media session. Do not use to stop or delete media.", schema, Tier.REVERSIBLE), pause),
    ]
