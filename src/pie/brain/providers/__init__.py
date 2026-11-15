from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, Literal

from pie.brain.types import AuthError, Message, ProviderError, ProviderReply, ToolSpec

_LOG = logging.getLogger(__name__)


class UnavailableProvider:
    """A configured cloud slot that fails explicitly instead of disappearing."""

    kind: Literal["cloud"] = "cloud"

    def __init__(self, name: str, error: ProviderError) -> None:
        self.name = name
        self.error = error

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
        raise self.error


def build_providers(config: Any) -> dict[str, Any]:
    providers: dict[str, Any] = {}
    if config.anthropic_model:
        try:
            from pie.brain.providers.anthropic_api import AnthropicProvider

            providers["anthropic"] = AnthropicProvider(config.anthropic_model)
        except AuthError as exc:
            _LOG.info("Anthropic provider has no configured credential")
            providers["anthropic"] = UnavailableProvider("anthropic", exc)
        except ImportError as exc:
            _LOG.info("Anthropic provider dependency unavailable: %s", type(exc).__name__)
    if config.openai_model:
        try:
            from pie.brain.providers.openai_api import OpenAIProvider

            providers["openai"] = OpenAIProvider(config.openai_model)
        except AuthError as exc:
            _LOG.info("OpenAI provider has no configured credential")
            providers["openai"] = UnavailableProvider("openai", exc)
        except ImportError as exc:
            _LOG.info("OpenAI provider dependency unavailable: %s", type(exc).__name__)
    try:
        from pie.brain.providers.local import LocalProvider

        providers["local"] = LocalProvider(
            backend=config.local_backend,
            model=config.local_model,
            max_ram_gb=config.local_max_ram_gb,
            keep_alive=config.local_keep_alive,
        )
    except ImportError as exc:
        _LOG.warning("Local provider dependencies unavailable: %s", type(exc).__name__)
    if config.cli_providers_enabled:
        from pie.brain.providers.claude_cli import ClaudeCliProvider
        from pie.brain.providers.codex_cli import CodexCliProvider

        providers["claude_cli"] = ClaudeCliProvider()
        providers["codex_cli"] = CodexCliProvider()
    return providers
