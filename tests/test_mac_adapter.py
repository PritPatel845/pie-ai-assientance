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


def test_media_commands_target_running_spotify_without_toggling_system_key() -> None:
    calls = []
    media_keys = []

    def fake(argv, **kwargs):
        calls.append((argv, kwargs))
        stdout = "Finder, Spotify, Terminal" if len(calls) == 1 else ""
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    controller = MacController(runner=fake, media_key=lambda: media_keys.append("playpause"))
    assert controller.stop_media()
    assert calls[0][0][0] == "/usr/bin/osascript"
    assert 'tell application "Spotify" to pause' in calls[1][0][2]
    assert media_keys == []


def test_media_commands_fall_back_to_injected_system_playpause_key() -> None:
    calls = []
    media_keys = []

    def fake(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout="Finder, Terminal", stderr="")

    controller = MacController(runner=fake, media_key=lambda: media_keys.append("playpause"))
    assert controller.play_media()
    assert len(calls) == 1
    assert media_keys == ["playpause"]


def test_media_commands_fall_back_when_running_player_script_fails() -> None:
    calls = []
    media_keys = []

    def fake(argv, **kwargs):
        calls.append((argv, kwargs))
        if len(calls) == 1:
            return subprocess.CompletedProcess(argv, 0, stdout="Finder, Music", stderr="")
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="not authorized")

    controller = MacController(runner=fake, media_key=lambda: media_keys.append("playpause"))
    assert controller.stop_media()
    assert media_keys == ["playpause"]
