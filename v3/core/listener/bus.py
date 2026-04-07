"""Lifecycle listener bus (register startup/shutdown handlers)."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Union

StartupHandler = Callable[[], Union[None, Awaitable[None]]]
ShutdownHandler = Callable[[], Union[None, Awaitable[None]]]


class ListenerBus:
    """Registers startup/shutdown callables; supports sync or async handlers."""

    def __init__(self) -> None:
        self._startup: list[StartupHandler] = []
        self._shutdown: list[ShutdownHandler] = []

    def add_startup(self, fn: StartupHandler) -> StartupHandler:
        self._startup.append(fn)
        return fn

    def add_shutdown(self, fn: ShutdownHandler) -> ShutdownHandler:
        self._shutdown.append(fn)
        return fn

    async def run_startup(self) -> None:
        for fn in self._startup:
            res = fn()
            if inspect.isawaitable(res):
                await res

    async def run_shutdown(self) -> None:
        for fn in reversed(self._shutdown):
            res = fn()
            if inspect.isawaitable(res):
                await res


listeners = ListenerBus()
