from __future__ import annotations

from pie.__main__ import build_parser


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
    args = build_parser().parse_args(
        ["--no-actions", "--no-voice", "tool", "run", "mac.close_app"]
    )
    assert args.no_actions is True
    assert args.no_voice is True
    assert args.config_action == "run"
    assert args.brain_args == ["mac.close_app"]
