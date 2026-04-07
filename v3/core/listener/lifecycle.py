"""Default core lifecycle listener wired to the global bus."""

from __future__ import annotations

from .bus import listeners


class CoreLifecycleListener:
    """Default lifecycle hooks for core (rules load, caches, background tasks, etc.)."""

    async def on_startup(self) -> None:
        pass

    async def on_shutdown(self) -> None:
        pass


_core = CoreLifecycleListener()


@listeners.add_startup
async def _core_startup() -> None:
    await _core.on_startup()


@listeners.add_shutdown
async def _core_shutdown() -> None:
    await _core.on_shutdown()
