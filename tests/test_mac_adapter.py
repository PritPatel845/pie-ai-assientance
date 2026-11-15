"""MacController adapter behaviour and application resolution
follow Phase 0S §3.5 (PDF pp. 20–21)."""

from __future__ import annotations

import subprocess

from pie.platform.mac import MacController, resolve_system_application


def test_aliases_and_substring_resolution() -> None:
    assert resolve_system_application("spotify") == "Spotify"
    assert resolve_system_application("open safari please") == "Safari"
    assert resolve_system_application("unknown app") is None


def test_mdfind_never_combines_capture_output_with_streams() -> None:
    calls = []

    def fake(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    controller = MacController(runner=fake)
    controller.open_application_or_item("An Unlisted App")
    assert calls
    for _, kwargs in calls:
        assert kwargs.get("capture_output") is True
        assert "stdout" not in kwargs
        assert "stderr" not in kwargs
        assert kwargs.get("shell") is False


def test_voice_activation_notification_uses_pie_title_and_duration() -> None:
    calls = []

    def fake(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    controller = MacController(runner=fake)
    assert controller.show_voice_activation(20)
    assert calls[0][0] == [
        "/usr/bin/osascript",
        "-e",
        'display notification "Listening for your command for 20 seconds." with title "PIE ACTIVE"',
    ]
    assert calls[0][1]["shell"] is False
