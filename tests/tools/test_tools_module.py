from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pie.config import load_config
from pie.events import EventBus
from pie.tools.module import ToolsModule


class FakeController:
    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"tool construction must not call controller.{name}")


def test_tools_module_registers_only_the_safe_builtin_catalog(tmp_path: Path) -> None:
    async def scenario() -> None:
        daemon = SimpleNamespace(
            bus=EventBus(asyncio.get_running_loop()),
            config=load_config(environ={}),
            tool_registry=None,
        )
        module = ToolsModule(FakeController())
        module.start(daemon)
        assert module.registry is not None
        names = {spec.name for spec in module.registry.list()}
        assert "shell.exec" not in names
        assert "terminal.run" not in names
        assert "mac.open_app" in names
        assert "fs.write_text" in names
        assert "voice.stop_listening" in names
        assert daemon.tool_registry is module.registry
        module.stop()
        assert daemon.tool_registry is None

    asyncio.run(scenario())
