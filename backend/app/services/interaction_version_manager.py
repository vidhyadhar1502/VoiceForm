import asyncio
from typing import Callable, List, Optional, Dict, Any
from datetime import datetime

class InteractionVersionManager:
    """
    Manages the monotonically increasing interaction version for the VoiceForm session.
    Guarantees thread-safe and async-safe versioning.
    """
    def __init__(self, initial_version: int = 10):
        self._active_version: int = initial_version
        self._lock: asyncio.Lock = asyncio.Lock()
        self._on_invalidation_listeners: List[Callable[[int, int], Any]] = []
        self._version_history: List[Dict[str, Any]] = [
            {
                "version": initial_version,
                "created_at": datetime.utcnow().isoformat(),
                "reason": "Initial Session Startup"
            }
        ]

    @property
    def active_version(self) -> int:
        return self._active_version

    def is_active(self, version: int) -> bool:
        """Returns True if and only if the specified version matches the current active version."""
        return version == self._active_version

    async def create_new_version(self, reason: str = "User Interaction") -> int:
        """
        Atomically increments the active interaction version, invalidates previous versions,
        and notifies invalidation listeners.
        """
        async with self._lock:
            old_version = self._active_version
            self._active_version += 1
            new_version = self._active_version
            
            self._version_history.append({
                "version": new_version,
                "created_at": datetime.utcnow().isoformat(),
                "reason": reason,
                "invalidated_version": old_version
            })

        # Notify listeners outside the lock
        for listener in self._on_invalidation_listeners:
            try:
                res = listener(old_version, new_version)
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
            except Exception as e:
                # Invalidation listener errors should not break state manager
                pass

        return new_version

    def add_invalidation_listener(self, listener: Callable[[int, int], Any]) -> None:
        """Register a callback invoked when old_version is invalidated by new_version."""
        self._on_invalidation_listeners.append(listener)

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._version_history)

    def reset(self, initial_version: int = 10) -> None:
        """Resets the version counter and history for a new session."""
        self._active_version = initial_version
        self._version_history = [
            {
                "version": initial_version,
                "created_at": datetime.utcnow().isoformat(),
                "reason": "Session Reset"
            }
        ]
