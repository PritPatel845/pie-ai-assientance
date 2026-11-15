"""Voice phrase matrix follows Phase 0S section 3.6."""

from __future__ import annotations

import pytest

from pie.inputs.voice.commands import extract_wake_command, parse_voice_command


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("stop listening", ("stop", None)),
        ("pause listening", ("stop", None)),
        ("voice off", ("stop", None)),
        ("confirm delete", ("delete", None)),
        ("yes delete", ("delete", None)),
        ("delete it", ("delete", None)),
        ("close window", ("close", None)),
        ("close app", ("close", None)),
        ("close application", ("close", None)),
        ("quit app", ("close", None)),
        ("hide window", ("hide", None)),
        ("hide app", ("hide", None)),
        ("undo", ("key", ("command", "z"))),
        ("undo that", ("key", ("command", "z"))),
        ("redo", ("key", ("command", "shift", "z"))),
        ("redo that", ("key", ("command", "shift", "z"))),
        ("copy", ("key", ("command", "c"))),
        ("copy that", ("key", ("command", "c"))),
        ("paste", ("key", ("command", "v"))),
        ("paste that", ("key", ("command", "v"))),
        ("select all", ("key", ("command", "a"))),
        ("select everything", ("key", ("command", "a"))),
        ("play", ("play", None)),
        ("play music", ("play", None)),
        ("resume music", ("play", None)),
        ("pause", ("pause", None)),
        ("pause music", ("pause", None)),
        ("stop music", ("pause", None)),
        ("mute", ("mute", None)),
        ("mute audio", ("mute", None)),
        ("silence", ("mute", None)),
        ("settings", ("settings", None)),
        ("system settings", ("settings", None)),
        ("system preferences", ("settings", None)),
        ("open settings", ("settings", None)),
        ("screenshot", ("screenshot", None)),
        ("take a screenshot", ("screenshot", None)),
        ("capture screen", ("screenshot", None)),
        ("lock screen", ("lock", None)),
        ("lock the screen", ("lock", None)),
        ("scroll up", ("scroll", 5)),
        ("page up", ("scroll", 5)),
        ("scroll down", ("scroll", -5)),
        ("page down", ("scroll", -5)),
        ("volume 150", ("volume", 100)),
        ("set volume 20", ("volume", 20)),
        ("set the volume to 5", ("volume", 5)),
        ("volume to 99", ("volume", 99)),
        ("search cats", ("search", "cats")),
        ("ask weather", ("search", "weather")),
        ("look up the web for Python", ("search", "python")),
        ("open safari", ("open", "safari")),
        ("launch notes", ("open", "notes")),
        ("start terminal", ("open", "terminal")),
        ("type hello world", ("type", "hello world")),
        ("write hello", ("type", "hello")),
        ("enter hello", ("type", "hello")),
        ("OPEN SAFARI", ("open", "safari")),
        ("  open    notes  ", ("open", "notes")),
        ("type   hello   world", ("type", "hello world")),
        ("volume 000", ("volume", 0)),
        ("volume 999", ("volume", 100)),
        ("set volume 007", ("volume", 7)),
        ("search the web for cats", ("search", "cats")),
        ("search google cats", ("search", "cats")),
        ("ask the web for weather", ("search", "weather")),
        ("look up google maps", ("search", "maps")),
        ("open https://example.com/?a=1&b=2", ("open", "https://example.com/?a=1&b=2")),
        ("type $(touch /tmp/pie-test)", ("type", "$(touch /tmp/pie-test)")),
        ("launch ~/Documents", ("open", "~/documents")),
        ("start /Applications/Safari.app", ("open", "/applications/safari.app")),
        ("volume -1", None),
        ("volume 1000", None),
        ("volume 1.5", None),
        ("search", None),
        ("ask", None),
        ("look up", None),
        ("open", None),
        ("launch", None),
        ("start", None),
        ("type", None),
        ("write", None),
        ("enter", None),
        ("scroll", None),
        ("delete", None),
        ("close", None),
        ("hide", None),
        ("pizza", None),
        ("unknown command", None),
    ],
)
def test_phrase_matrix(phrase, expected) -> None:
    assert parse_voice_command(phrase) == expected


@pytest.mark.parametrize("wake", ["pie", "hey pie", "pi", "jr", "j r", "jay r", "jarvis"])
def test_all_wake_words(wake: str) -> None:
    assert extract_wake_command(wake + ", open safari") == "open safari"


@pytest.mark.parametrize("not_wake", ["pizza", "pied", "pine", "spider"])
def test_wake_word_prefixes_do_not_false_trigger(not_wake: str) -> None:
    assert extract_wake_command(not_wake) is None


def test_wake_word_punctuation_and_empty_remainder() -> None:
    assert extract_wake_command("HEY PIE!") == ""
    assert extract_wake_command("Pie,") == ""
    assert extract_wake_command("hello pie open safari") is None


def test_hostile_text_is_data_not_shell() -> None:
    assert parse_voice_command("open ; rm -rf ~") == ("open", "; rm -rf ~")


@pytest.mark.parametrize("separator", [",", ".", "!", "?", ";", ":", "-", ")"])
def test_wake_word_accepts_punctuation_boundaries(separator: str) -> None:
    assert extract_wake_command(f"pie{separator} open safari") == "open safari"
