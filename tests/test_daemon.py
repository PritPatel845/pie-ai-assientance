from __future__ import annotations

import time
from dataclasses import FrozenInstanceError

import pytest

from pie.config import Config
from pie.core.daemon import Daemon
from pie.core.state import RuntimeState, StopFlag


class RecordingModule:
    def __init__(self, name: str, log: list[str], fail: bool = False) -> None:
        self.name, self.log, self.fail = name, log, fail

    def start(self, daemon: Daemon) -> None:
        self.log.append(f"start:{self.name}")
        if self.fail:
            raise ValueError("startup failure")

    def stop(self) -> None:
        self.log.append(f"stop:{self.name}")


def test_daemon_start_stop_order_and_idempotence() -> None:
    log: list[str] = []
    daemon = Daemon(Config())
    daemon.register_module(RecordingModule("one", log))
    daemon.register_module(RecordingModule("two", log))
    daemon.run_main(lambda: None)
    daemon.stop()
    assert log == ["start:one", "start:two", "stop:two", "stop:one"]


def test_startup_failure_rolls_back_started_modules() -> None:
    log: list[str] = []
    daemon = Daemon(Config())
    daemon.register_module(RecordingModule("first", log))
    daemon.register_module(RecordingModule("broken", log, fail=True))
    with pytest.raises(RuntimeError, match="startup failed"):
        daemon.start()
    assert log == ["start:first", "start:broken", "stop:first"]


def test_hanging_module_stop_is_bounded() -> None:
    class Hanging:
        name = "hanging"

        def start(self, daemon: Daemon) -> None:
            return None

        def stop(self) -> None:
            time.sleep(4)

    daemon = Daemon(Config())
    daemon.register_module(Hanging())
    daemon.start()
    started = time.monotonic()
    daemon.stop()
    assert time.monotonic() - started < 3.0


def test_runtime_state_snapshots_are_immutable_and_thread_safe() -> None:
    state = RuntimeState()
    state.update(
        mode="game",
        game_profile="counter-strike",
        armed=True,
        last_gesture="OPEN PALM",
    )
    snapshot = state.snapshot()
    assert snapshot.mode == "game"
    assert snapshot.game_profile == "counter-strike"
    assert snapshot.armed is True
    with pytest.raises(FrozenInstanceError):
        snapshot.mode = "idle"  # type: ignore[misc]

    flag = StopFlag()
    assert not flag.is_set()
    flag.set()
    assert flag.is_set()
    assert flag.wait(0)
