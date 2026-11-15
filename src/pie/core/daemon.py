from __future__ import annotations

import asyncio
import logging
import signal
import threading
from collections.abc import Awaitable
from typing import Protocol

from pie.core.events import EventBus
from pie.core.state import RuntimeState, StopFlag

_LOG = logging.getLogger(__name__)


class Module(Protocol):
    def start(self) -> None | Awaitable[None]: ...
    def stop(self) -> None | Awaitable[None]: ...


class Daemon:
    """Owns the asyncio loop thread and coordinates ordered module lifecycle."""

    def __init__(self, modules: list[Module] | None = None) -> None:
        self.stop_flag = StopFlag()
        self.state = RuntimeState()
        self._modules = list(modules or [])
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._lock = threading.RLock()
        self.events: EventBus | None = None
        self._started: list[Module] = []

    def add_module(self, module: Module) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise RuntimeError("cannot add modules after daemon start")
            self._modules.append(module)

    def start(self, timeout: float = 5.0) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self.stop_flag = StopFlag()
            self._ready.clear()
            self._thread = threading.Thread(target=self._thread_main, name="pie-loop", daemon=True)
            self._thread.start()
        if not self._ready.wait(timeout):
            self.stop()
            raise TimeoutError("Pie daemon event loop did not start")
        if self._loop is None:
            raise RuntimeError("Pie daemon failed to initialise its event loop")
        future = asyncio.run_coroutine_threadsafe(self._start_modules(), self._loop)
        try:
            future.result(timeout=timeout)
        except Exception:
            self.stop()
            raise
        self.state.update(running=True, mode="idle")

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self.events = EventBus(loop)
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
            self._loop = None

    async def _start_modules(self) -> None:
        for module in self._modules:
            try:
                result = module.start()
                if asyncio.iscoroutine(result):
                    await result
                self._started.append(module)
            except Exception:
                _LOG.exception("Module startup failed; rolling back")
                await self._stop_modules()
                raise

    async def _stop_modules(self) -> None:
        for module in reversed(self._started):
            try:
                result = module.stop()
                if asyncio.iscoroutine(result):
                    await asyncio.wait_for(result, timeout=3.0)
            except Exception:
                _LOG.exception("Module shutdown failed")
        self._started.clear()

    def stop(self, timeout: float = 12.0) -> None:
        self.stop_flag.request()
        loop = self._loop
        thread = self._thread
        if loop is None or thread is None:
            return
        async def shutdown() -> None:
            await self._stop_modules()
            if self.events:
                await self.events.close(timeout=3.0)
            self.state.update(running=False, mode="idle")
        try:
            asyncio.run_coroutine_threadsafe(shutdown(), loop).result(timeout=timeout - 1)
        except Exception:
            _LOG.exception("Daemon shutdown encountered an error")
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=max(0.1, timeout - 1))
        if thread.is_alive():
            _LOG.error("Daemon event loop thread did not stop within timeout")
        self._thread = None

    def install_signal_handlers(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("signal handlers must be installed from the main thread")
        signal.signal(signal.SIGINT, lambda *_: self.stop_flag.request())
        signal.signal(signal.SIGTERM, lambda *_: self.stop_flag.request())

    def wait(self, poll_interval: float = 0.1) -> None:
        self.stop_flag.wait()
        self.stop()
