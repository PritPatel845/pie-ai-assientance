from pie.core.state import RuntimeState, StopFlag


def test_stop_flag_is_idempotent() -> None:
    flag = StopFlag()
    assert not flag.is_set()
    flag.request()
    flag.request()
    assert flag.is_set()


def test_runtime_state_returns_snapshot() -> None:
    state = RuntimeState()
    state.update(mode="listening", running=True, values={"count": 2})
    snapshot = state.snapshot()
    assert snapshot.mode == "listening"
    assert snapshot.running
    assert dict(snapshot.values) == {"count": 2}
