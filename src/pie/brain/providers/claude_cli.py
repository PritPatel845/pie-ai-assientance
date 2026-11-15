from __future__ import annotations

from collections.abc import Sequence

from pie.brain.types import Message, ProviderReply, ProviderUnavailable, ToolSpec


class ClaudeCliProvider:
    """Deliberately disabled until Claude CLI can be sandboxed without file or shell access."""

    name = "claude_cli"
    kind = "cloud"

    async def healthcheck(self) -> bool:
        return True

    async def complete(
        self,
        messages: Sequence[Message],
        tools: list[ToolSpec],
        *,
        max_tokens: int,
        timeout_s: float,
    ) -> ProviderReply:
        del messages, tools, max_tokens, timeout_s
        raise ProviderUnavailable(self.name, "unsafe: cannot sandbox Claude CLI")
