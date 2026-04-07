"""Application lifecycle listeners (package)."""

from __future__ import annotations

from .bus import ListenerBus, listeners
from .lifecycle import CoreLifecycleListener  # loads module → registers default hooks

__all__ = ["CoreLifecycleListener", "ListenerBus", "listeners"]
