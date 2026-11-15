from __future__ import annotations

import asyncio
import inspect
import logging
import signal
import threading
from collections.abc import Callable
from typing import cast, Protocol

from pie import __version__
from pie.config import Config
from pie.core.state import RuntimeState, StopFlag
from pie.events import EventBus

_LOG = logging.getLogger(__name__)


class Module(Protocol):
    name: str

    def start(self, daemon: Daemon) -> None: ...
    def stop(self) -> object: ...


class Daemon:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.state = RuntimeState()
        self.stop_flag = StopFlag()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.bus: EventBus | None = None
        self._modules: list[Module] = []
        self._started: list[Module] = []
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._lifecycle_lock = threading.RLock()
        self._started_once = False
        self._stopped = False

    def register_module(self, module: Module) -> None:
        with self._lifecycle_lock:
            if self._started_once:
                raise RuntimeError("modules must be registered before daemon start")
            self._modules.append(module)

    def _loop_thread(self) -> None:
        loop = asyncio.new_event_loop()
        self.loop = loop
        asyncio.set_event_loop(loop)
        self.bus = EventBus(loop)
        loop.call_soon(self._ready.set)
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    def start(self) -> None:
        with self._lifecycle_lock:
            if self._started_once:
                return
            self._started_once = True
            self._thread = threading.Thread(target=self._loop_thread, name="pie-loop", daemon=True)
            self._thread.start()
        if not self._ready.wait(3.0) or self.loop is None or self.bus is None:
            self.stop()
            raise RuntimeError("asyncio loop failed to start")
        try:
            for module in self._modules:
                module.start(self)
                self._started.append(module)
            self.bus.publish("system.started", {"version": __version__}, source="daemon")
            if threading.current_thread() is threading.main_thread():
                for signum in (signal.SIGINT, signal.SIGTERM):
                    signal.signal(signum, self._signal_stop)
        except Exception as exc:
            self.stop()
            message = f"daemon module startup failed: {type(exc).__name__}: {exc}"
            raise RuntimeError(message) from exc

    def _signal_stop(self, signum: int, frame: object) -> None:
        self.stop_flag.set()

    def run_main(self, main_thread_fn: Callable[[], None] | None = None) -> None:
        self.start()
        try:
            if main_thread_fn is not None:
                main_thread_fn()
            else:
                self.stop_flag.wait()
        finally:
            self.stop()

    def stop(self) -> None:
        with self._lifecycle_lock:
            if self._stopped:
                return
            self._stopped = True
        if self.bus is not None:
            self.bus.publish("system.stopping", {}, source="daemon")
        self.stop_flag.set()
        for module in reversed(self._started):
            try:
                loop = cast(asyncio.AbstractEventLoop, self.loop)
                if not loop.is_running():
                    module.stop()
                    continue

                async def stop_one(
                    target: Module = module,
                    event_loop: asyncio.AbstractEventLoop = loop,
                ) -> None:
                    result = await event_loop.run_in_executor(None, target.stop)
                    if inspect.isawaitable(result):
                        await result

                future = asyncio.run_coroutine_threadsafe(
                    asyncio.wait_for(stop_one(), timeout=2.5), loop
                )
                future.result(timeout=2.7)
            except Exception:
                _LOG.exception("module %s failed to stop", module.name)
        self._started.clear()
        if self.loop is not None and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=3.0)
            if self._thread.is_alive():
                _LOG.error("pie-loop thread did not stop within 3 seconds")
