from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pie.__main__ import build_parser
from pie.safety.permissions import Tier
from pie.tools.cli import _requires_confirmation


def test_tool_cli_preserves_json_and_dry_run_options() -> None:
    args = build_parser().parse_args(
        [
            "tool",
            "run",
            "mac.open_app",
            "--args-json",
            '{"name":"Safari"}',
            "--dry-run",
        ]
    )
    assert args.command == "tool"
    assert args.config_action == "run"
    assert args.brain_args == [
        "mac.open_app",
        "--args-json",
        '{"name":"Safari"}',
        "--dry-run",
    ]


def test_audit_cli_preserves_tail_options() -> None:
    args = build_parser().parse_args(["audit", "tail", "-n", "25"])
    assert args.command == "audit"
    assert args.config_action == "tail"
    assert args.brain_args == ["-n", "25"]


def test_global_no_actions_and_no_voice_flags_are_preserved() -> None:
    args = build_parser().parse_args(["--no-actions", "--no-voice", "tool", "run", "mac.close_app"])
    assert args.no_actions is True
    assert args.voice is False
    assert args.config_action == "run"
    assert args.brain_args == ["mac.close_app"]


def _filesystem_tool() -> SimpleNamespace:
    return SimpleNamespace(
        spec=SimpleNamespace(
            tier=Tier.REVERSIBLE,
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "x-path": True,
                        "x-confirm-if-exists": True,
                        "x-confirm-outside-sandbox": True,
                    },
                    "content": {"type": "string"},
                },
            },
        )
    )


def _path_config(sandbox: Path, audit: Path) -> SimpleNamespace:
    return SimpleNamespace(
        safety=SimpleNamespace(
            sandbox_dir=str(sandbox),
            allowed_folders=(str(sandbox),),
            audit_path=str(audit),
        )
    )


def test_new_file_inside_sandbox_does_not_start_voice_approval(tmp_path: Path) -> None:
    sandbox = tmp_path / "PieWorkspace"
    sandbox.mkdir()
    tool = _filesystem_tool()
    config = _path_config(sandbox, tmp_path / "audit.jsonl")

    assert not _requires_confirmation(
        tool, {"path": str(sandbox / "new.txt"), "content": "safe"}, config
    )


def test_overwrite_inside_sandbox_requires_voice_approval(tmp_path: Path) -> None:
    sandbox = tmp_path / "PieWorkspace"
    sandbox.mkdir()
    existing = sandbox / "existing.txt"
    existing.write_text("original", encoding="utf-8")

    assert _requires_confirmation(
        _filesystem_tool(),
        {"path": str(existing), "content": "replacement"},
        _path_config(sandbox, tmp_path / "audit.jsonl"),
    )


def test_write_outside_sandbox_requires_voice_approval(tmp_path: Path) -> None:
    sandbox = tmp_path / "PieWorkspace"
    sandbox.mkdir()
    outside = tmp_path / "Documents" / "new.txt"

    assert _requires_confirmation(
        _filesystem_tool(),
        {"path": str(outside), "content": "outside"},
        _path_config(sandbox, tmp_path / "audit.jsonl"),
    )


def test_protected_path_is_rejected_without_starting_voice_approval(tmp_path: Path) -> None:
    sandbox = tmp_path / "PieWorkspace"
    sandbox.mkdir()
    home = tmp_path / "home"
    (home / ".ssh").mkdir(parents=True)

    assert not _requires_confirmation(
        _filesystem_tool(),
        {"path": str(home / ".ssh" / "id_rsa")},
        _path_config(sandbox, tmp_path / "audit.jsonl"),
    )


def test_tool_command_configures_application_logging(monkeypatch) -> None:
    from pie.tools import cli as tool_cli

    calls: list[str] = []
    monkeypatch.setattr(tool_cli, "load_config", lambda _path: SimpleNamespace(
        app=SimpleNamespace(log_level="DEBUG")
    ))
    monkeypatch.setattr(tool_cli, "configure_logging", calls.append)
    monkeypatch.setattr(tool_cli, "Daemon", lambda _config: SimpleNamespace())
    monkeypatch.setattr(tool_cli, "ToolsModule", lambda: SimpleNamespace())
    monkeypatch.setattr(tool_cli, "_requires_confirmation", lambda *_args: False)
    # An invalid action exits before daemon startup but after logging setup.
    try:
        tool_cli.run_tool_command("invalid", [], None)
    except ValueError:
        pass
    assert calls == ["DEBUG"]
