"""Game profile key mappings follow Phase 0S section 3.2."""

from __future__ import annotations

from pie.inputs.gesture.game import GAME_PROFILES, MAC_KEY_CODES, GameController


class Poster:
    def __init__(self):
        self.events = []

    def key_event(self, code: int, pressed: bool) -> None:
        self.events.append((code, pressed))


def test_profiles_match_contract() -> None:
    assert GAME_PROFILES["asphalt"]["accelerate"] == "up"
    assert GAME_PROFILES["temple-run"]["slide"] == "down"
    assert GAME_PROFILES["counter-strike"]["forward"] == "w"
    assert MAC_KEY_CODES["space"] == 49


def test_controller_is_idempotent_and_releases_keys() -> None:
    poster = Poster()
    game = GameController("asphalt", poster)
    game.set_key("left", True)
    game.set_key("left", True)
    assert poster.events == [(123, True)]
    game.release_all()
    assert poster.events == [(123, True), (123, False)]
    assert game.held_keys == frozenset()
