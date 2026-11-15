from __future__ import annotations

from pie.__main__ import build_parser


def test_brain_cli_subcommands_parse_provider_and_prompt() -> None:
    args = build_parser().parse_args(["brain", "test", "anthropic"])
    assert args.command == "brain"
    assert args.config_action == "test"
    assert args.brain_args == ["anthropic"]

    ask = build_parser().parse_args(["brain", "ask", "what", "is", "2+2"])
    assert ask.config_action == "ask"
    assert ask.brain_args == ["what", "is", "2+2"]


def test_quota_cli_parses_reset_all() -> None:
    args = build_parser().parse_args(["quota", "reset", "all"])
    assert args.command == "quota"
    assert args.config_action == "reset"
    assert args.brain_args == ["all"]
