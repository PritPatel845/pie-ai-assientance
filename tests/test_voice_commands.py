from pie.inputs.voice.commands import extract_wake_command, parse_voice_command


def test_wake_word_extracts_command() -> None:
    assert extract_wake_command("Hey Pie, open Safari") == "open safari"


def test_wake_word_without_command() -> None:
    assert extract_wake_command("Pie") == ""


def test_volume_is_clamped() -> None:
    assert parse_voice_command("volume 140") == ("volume", 100)


def test_unrecognised_text_is_not_executed() -> None:
    assert parse_voice_command("run arbitrary shell") is None
