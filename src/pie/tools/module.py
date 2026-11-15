from __future__ import annotations

from pathlib import Path
from typing import Any

from pie.core.daemon import Daemon
from pie.platform.mac import MacController
from pie.safety.audit import AuditLog
from pie.safety.permissions import PermissionGate
from pie.tools.builtin.filesystem import build_filesystem_tools
from pie.tools.builtin.mac import build_mac_tools
from pie.tools.builtin.media import build_media_tools
from pie.tools.builtin.system import build_system_tools
from pie.tools.builtin.voice import build_voice_tools
from pie.tools.registry import ToolRegistry


class ToolsModule:
    """Owns the one registry, permission gate, and append-only audit log."""

    name = "tools"

    def __init__(self, controller: MacController | None = None) -> None:
        self.controller = controller or MacController()
        self.registry: ToolRegistry | None = None
        self.permission_gate: PermissionGate | None = None
        self.audit: AuditLog | None = None
        self.daemon: Daemon | None = None

    def start(self, daemon: Daemon) -> None:
        if daemon.bus is None:
            raise RuntimeError("tools require the daemon event bus")
        self.daemon = daemon
        config = daemon.config
        self.permission_gate = PermissionGate(
            daemon.bus,
            timeout_s=config.safety.confirm_timeout_s,
            max_prompts_per_min=config.safety.max_confirm_prompts_per_min,
        )
        self.permission_gate.start()
        self.audit = AuditLog(Path(config.safety.audit_path).expanduser())
        self.registry = ToolRegistry(config, daemon.bus, self.permission_gate, self.audit)
        for tool in (
            *build_system_tools(self.controller),
            *build_filesystem_tools(),
            *build_mac_tools(self.controller),
            *build_media_tools(self.controller),
            *build_voice_tools(daemon.bus),
        ):
            self.registry.register(tool)
        daemon.tool_registry = self.registry

    def stop(self) -> None:
        if self.permission_gate is not None:
            self.permission_gate.stop()
        if self.daemon is not None:
            self.daemon.tool_registry = None
        self.registry = None
        self.permission_gate = None
        self.audit = None
        self.daemon = None


__all__ = ["ToolsModule"]
