from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from pie.config import load_config
from pie.core.daemon import Daemon
from pie.inputs.voice.pipeline import VoiceController
from pie.platform.mac import MacController
from pie.safety.paths_guard import PathGuardError, guard_paths
from pie.safety.permissions import Tier
from pie.tools.module import ToolsModule


class _VoiceApprovalModule:
    name = "voice-approval"

    def __init__(self) -> None:
        self.controller: VoiceController | None = None

    def start(self, daemon: Daemon) -> None:
        self.controller = VoiceController(
            MacController(),
            bus=daemon.bus,
            config=daemon.config.voice,
            brain_enabled=True,
        )
        self.controller.start()

    def stop(self) -> None:
        if self.controller is not None:
            self.controller.stop()
            self.controller = None


def _requires_confirmation(tool: Any, payload: dict[str, Any], config: Any) -> bool:
    """Predict the registry's confirmation tier before starting voice approval.

    Invalid or protected paths deliberately return False here: the registry
    remains authoritative and rejects them before requesting permission.
    """
    tier = tool.spec.tier
    if tier is Tier.CONFIRM:
        return True

    properties = tool.spec.parameters.get("properties", {})
    sandbox = Path(str(config.safety.sandbox_dir)).expanduser()
    args = dict(payload)
    try:
        for key, property_schema in properties.items():
            raw_path = args.get(key)
            if (
                isinstance(property_schema, dict)
                and property_schema.get("x-path") is True
                and isinstance(raw_path, str)
                and not raw_path.startswith("~")
                and not Path(raw_path).is_absolute()
            ):
                args[key] = str(sandbox / raw_path)

        path_tier = guard_paths(
            args,
            tool.spec.parameters,
            allowed_folders=config.safety.allowed_folders,
            audit_path=config.safety.audit_path,
        )
        tier = max(tier, path_tier)
        for key, property_schema in properties.items():
            if not isinstance(property_schema, dict) or not isinstance(args.get(key), str):
                continue
            candidate = Path(str(args[key])).expanduser()
            if property_schema.get("x-confirm-if-exists") is True and candidate.exists():
                tier = max(tier, Tier.CONFIRM)
            if property_schema.get("x-confirm-outside-sandbox") is True:
                try:
                    candidate.resolve().relative_to(sandbox.resolve())
                except ValueError:
                    tier = max(tier, Tier.CONFIRM)
    except (PathGuardError, TypeError, ValueError):
        # Do not start the microphone for a request that the registry will deny.
        return False
    return bool(tier >= Tier.CONFIRM)


def run_tool_command(
    action: str | None,
    arguments: list[str],
    config_path: Path | None,
    *,
    no_voice: bool = False,
    no_actions: bool = False,
) -> int:
    config = load_config(config_path)
    if no_actions:
        config = replace(config, tools=replace(config.tools, dry_run=True))
    tools_module = ToolsModule()
    daemon = Daemon(config)
    daemon.register_module(tools_module)
    voice_module: _VoiceApprovalModule | None = None
    try:
        if action == "list":
            daemon.start()
            assert tools_module.registry is not None
            for spec in tools_module.registry.list():
                print(f"{spec.name}\t{spec.tier.name}\t{spec.description}")
            return 0
        if action != "run" or not arguments:
            raise ValueError(
                'use: pie tool list | pie tool run <name> --args-json "{}" [--dry-run]'
            )
        name = arguments[0]
        parser = argparse.ArgumentParser(prog="pie tool run")
        parser.add_argument("--args-json", default="{}")
        parser.add_argument("--dry-run", action="store_true")
        parsed = parser.parse_args(arguments[1:])
        payload: Any = json.loads(parsed.args_json)
        if not isinstance(payload, dict):
            raise ValueError("--args-json must contain a JSON object")
        daemon.start()
        assert tools_module.registry is not None and daemon.loop is not None
        tool = tools_module.registry.get(name)
        if tool is None:
            print(json.dumps({"ok": False, "error": "unknown tool"}))
            return 1
        dry_run = bool(config.tools.dry_run or parsed.dry_run)
        if parsed.dry_run:
            config = replace(config, tools=replace(config.tools, dry_run=True))
        may_need_confirmation = _requires_confirmation(tool, payload, config)
        if may_need_confirmation and not dry_run and not no_voice and config.voice.enabled:
            voice_module = _VoiceApprovalModule()
            voice_module.start(daemon)
            print("Confirmation required. Say yes or no.")
        elif may_need_confirmation and not dry_run and (no_voice or not config.voice.enabled):
            print("Voice approval is disabled; requests will fail closed without UI approval.")
        future = asyncio.run_coroutine_threadsafe(
            tools_module.registry.execute(name, payload, source="text", dry_run=dry_run),
            daemon.loop,
        )
        result = future.result(timeout=tool.spec.timeout_s + config.safety.confirm_timeout_s + 5)
        print(
            json.dumps(
                {
                    "ok": result.ok,
                    "output": result.output,
                    "error": result.error,
                    "artifacts": result.artifacts,
                },
                ensure_ascii=False,
                default=str,
            )
        )
        return 0 if result.ok else 1
    finally:
        if voice_module is not None:
            voice_module.stop()
        daemon.stop()


def run_audit_command(action: str | None, arguments: list[str], config_path: Path | None) -> int:
    if action != "tail":
        raise ValueError("use: pie audit tail [-n 50]")
    parser = argparse.ArgumentParser(prog="pie audit tail")
    parser.add_argument("-n", type=int, default=50)
    parsed = parser.parse_args(arguments)
    if not 1 <= parsed.n <= 1000:
        raise ValueError("-n must be between 1 and 1000")
    path = Path(load_config(config_path).safety.audit_path).expanduser()
    if not path.is_file():
        print("No audit records yet.")
        return 0
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines[-parsed.n :]:
        print(line)
    return 0


__all__ = ["run_audit_command", "run_tool_command"]
