import asyncio

from pie.core.daemon import Daemon


def test_daemon_starts_and_stops_modules_in_order() -> None:
    calls: list[str] = []

    class FakeModule:
        def __init__(self, name: str) -> None:
            self.name = name

        async def start(self) -> None:
            calls.append("start:" + self.name)

        async def stop(self) -> None:
            await asyncio.sleep(0)
            calls.append("stop:" + self.name)

    daemon = Daemon([FakeModule("a"), FakeModule("b")])
    daemon.start()
    assert daemon.state.snapshot().running
    daemon.stop()
    assert calls == ["start:a", "start:b", "stop:b", "stop:a"]
