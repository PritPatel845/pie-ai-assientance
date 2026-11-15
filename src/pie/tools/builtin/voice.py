from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pie.events import EventBus
from pie.safety.permissions import Tier
from pie.tools.base import FunctionTool, ToolContext, ToolResult, ToolSpec, ok


def build_voice_tools(bus: EventBus) -> list[FunctionTool]:
    async def stop_listening(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        del args
        if ctx.dry_run:
            return ok({"would_stop_listening": True})
        bus.publish("voice.stop_listening", {}, source="tool", correlation_id=ctx.call_id)
        return ok({"listening": False})

    return [
        FunctionTool(
            ToolSpec("voice.stop_listening", "Stop the current voice listening window without stopping Pie. Do not use to shut down the daemon.", {
                "type": "object", "properties": {}, "additionalProperties": False
            }, Tier.READ),
            stop_listening,
        )
    ]
