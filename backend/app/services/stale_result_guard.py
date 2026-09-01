import asyncio
from typing import Callable, Any, Optional, Dict, List
from datetime import datetime
from backend.app.services.interaction_version_manager import InteractionVersionManager
from backend.app.services.task_manager import TaskManager

class StaleResultBlockedException(Exception):
    """Raised when an operation attempt is blocked by the version fence."""
    def __init__(self, operation_version: int, active_version: int, task_name: str = ""):
        self.operation_version = operation_version
        self.active_version = active_version
        self.task_name = task_name
        super().__init__(
            f"Stale result blocked: operation version {operation_version} is superseded by active version {active_version} ({task_name})"
        )

class StaleResultGuard:
    """
    Guarantees state correctness by preventing stale asynchronous results,
    LLM outputs, tool responses, and audio playbacks from mutating application state.
    
    Principle: 'Cancellation improves efficiency, but version fencing guarantees correctness.'
    """
    def __init__(self, version_manager: InteractionVersionManager, task_manager: Optional[TaskManager] = None):
        self.version_manager = version_manager
        self.task_manager = task_manager
        self._stale_blocks_count: int = 0
        self._blocked_events: List[Dict[str, Any]] = []
        self._on_stale_callbacks: List[Callable[[int, int, str, Optional[Dict[str, Any]]], Any]] = []

    def can_apply_result(self, operation_version: int) -> bool:
        """
        Synchronous check if an operation is still valid for the active version.
        Returns True if operation_version matches the current active_version.
        """
        return self.version_manager.is_active(operation_version)

    async def verify_and_apply(
        self,
        operation_version: int,
        task_id: Optional[str],
        task_name: str,
        apply_fn: Callable[[], Any],
        payload_details: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Fences an operation. If the version is current, executes apply_fn.
        If stale, blocks execution, logs stale event, increments counter,
        and marks task as STALE_BLOCKED in the task registry.
        """
        active_ver = self.version_manager.active_version
        if operation_version != active_ver:
            self._stale_blocks_count += 1
            blocked_record = {
                "timestamp": datetime.utcnow().isoformat(),
                "task_id": task_id,
                "task_name": task_name,
                "operation_version": operation_version,
                "active_version": active_ver,
                "details": payload_details
            }
            self._blocked_events.append(blocked_record)

            if self.task_manager and task_id:
                await self.task_manager.mark_stale_blocked(task_id)

            # Fire on_stale callbacks (for event log / UI stream)
            for cb in self._on_stale_callbacks:
                try:
                    res = cb(operation_version, active_ver, task_name, payload_details)
                    if asyncio.iscoroutine(res):
                        asyncio.create_task(res)
                except Exception:
                    pass

            return {
                "success": False,
                "stale_blocked": True,
                "operation_version": operation_version,
                "active_version": active_ver,
                "message": f"Result for version {operation_version} blocked by fence (active: {active_ver})"
            }

        # Operation is fresh - execute the state mutation
        if asyncio.iscoroutinefunction(apply_fn):
            result = await apply_fn()
        else:
            result = apply_fn()

        if self.task_manager and task_id:
            await self.task_manager.mark_completed(task_id, result if isinstance(result, dict) else None)

        return {
            "success": True,
            "stale_blocked": False,
            "operation_version": operation_version,
            "result": result
        }

    def register_stale_listener(self, callback: Callable[[int, int, str, Optional[Dict[str, Any]]], Any]) -> None:
        self._on_stale_callbacks.append(callback)

    @property
    def stale_blocks_count(self) -> int:
        return self._stale_blocks_count

    def get_blocked_events(self) -> List[Dict[str, Any]]:
        return list(self._blocked_events)
