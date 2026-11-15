from pie.inputs.gesture.game import GAME_PROFILES, GameController


class Poster:
    def __init__(self) -> None:
        self.events: list[tuple[int, bool]] = []

    def key_event(self, code: int, pressed: bool) -> None:
        self.events.append((code, pressed))


def test_profiles_are_available() -> None:
    assert set(GAME_PROFILES) == {"asphalt", "temple-run", "counter-strike"}


def test_game_controller_releases_held_keys() -> None:
    poster = Poster()
    controller = GameController("asphalt", poster)
    controller.set_key("left", True)
    controller.release_all()
    assert poster.events == [(123, True), (123, False)]
    assert controller.held_keys == frozenset()
