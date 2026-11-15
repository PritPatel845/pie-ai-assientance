"""CLI flags, config precedence, and doctor/version surfaces follow Phase 0S §3.9 (PDF p. 23)."""

from __future__ import annotations

from pie import __main__ as cli
from pie.config import Config, GestureConfig, VoiceConfig


def test_cli_flags_defer_to_config_when_omitted() -> None:
    args = cli.build_parser().parse_args([])
    assert args.camera is None
    assert args.steer_sensitivity is None
    assert args.voice is None
    assert args.voice_listen_seconds is None


def test_main_uses_config_values_without_cli_overrides(monkeypatch, capsys) -> None:
    config = Config(
        gesture=GestureConfig(
            camera=2,
            preview=False,
            arm_hold_seconds=1.5,
            steer_sensitivity=0.012,
        ),
        voice=VoiceConfig(enabled=False, listen_seconds=25),
    )
    calls: dict[str, object] = {}
    monkeypatch.setattr(cli, "load_config", lambda path: config)
    monkeypatch.setattr(cli, "configure_logging", lambda level: None)
    monkeypatch.setattr(cli, "run", lambda **kwargs: calls.update(kwargs))
    assert cli.main([]) == 0
    assert calls["camera"] == 2
    assert calls["steer_sensitivity"] == 0.012
    assert calls["preview"] is False
    assert "Voice capture arrives" not in capsys.readouterr().out


def test_explicit_cli_values_override_config(monkeypatch, capsys) -> None:
    config = Config(
        gesture=GestureConfig(camera=2, steer_sensitivity=0.012),
        voice=VoiceConfig(enabled=False),
    )
    calls: dict[str, object] = {}
    monkeypatch.setattr(cli, "load_config", lambda path: config)
    monkeypatch.setattr(cli, "configure_logging", lambda level: None)
    monkeypatch.setattr(cli, "run", lambda **kwargs: calls.update(kwargs))
    assert cli.main(["--camera", "5", "--steer-sensitivity", "0.02", "--voice"]) == 0
    assert calls["camera"] == 5
    assert calls["steer_sensitivity"] == 0.02
    assert "Voice capture arrives" not in capsys.readouterr().out


def test_doctor_reports_import_errors_without_crashing(monkeypatch, tmp_path, capsys) -> None:
    def broken_import(_name):
        raise RuntimeError("native library load failed")

    monkeypatch.setattr(cli.importlib, "import_module", broken_import)
    monkeypatch.setattr(cli, "resolve_model_path", lambda: None)
    monkeypatch.setattr(cli, "pie_home", lambda: tmp_path / ".pie")
    monkeypatch.setattr(cli, "state_dir", lambda: tmp_path / ".pie" / "state")
    monkeypatch.setattr(cli, "logs_dir", lambda: tmp_path / ".pie" / "logs")
    monkeypatch.setattr(cli, "models_dir", lambda: tmp_path / ".pie" / "models")
    monkeypatch.setattr(cli, "learning_dir", lambda: tmp_path / ".pie" / "learning")
    assert cli.doctor() == 0
    output = capsys.readouterr().out
    assert "cv2: FAIL (RuntimeError: native library load failed)" in output
    assert "NOT FOUND" in output
    assert not (tmp_path / ".pie").exists()
