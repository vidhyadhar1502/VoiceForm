import asyncio
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from backend.app.models.task_models import TaskRecord, TaskStatus

class TaskManager:
    """
    Tracks and manages asynchronous background tasks (LLM, validation, TTS, tools)
    associated with interaction versions. Supports cooperative cancellation.
    """
    def __init__(self):
        self._tasks: Dict[str, TaskRecord] = {}
        self._asyncio_handles: Dict[str, asyncio.Task] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    async def register_task(
        self,
        name: str,
        version: int,
        target_field: Optional[str] = None,
        asyncio_task: Optional[asyncio.Task] = None,
        payload: Optional[Dict[str, Any]] = None,
        uncancellable: bool = False,
        task_id: Optional[str] = None,
    ) -> TaskRecord:
        """Register a new asynchronous operation tagged with its request version."""
        tid = task_id or f"task_{uuid.uuid4().hex[:8]}"
        record = TaskRecord(
            task_id=tid,
            name=name,
            target_field=target_field,
            version=version,
            status=TaskStatus.ACTIVE,
            created_at=datetime.utcnow().isoformat(),
            payload=payload,
            uncancellable=uncancellable
        )

        async with self._lock:
            self._tasks[tid] = record
            if asyncio_task:
                self._asyncio_handles[tid] = asyncio_task

        return record

    async def mark_completed(self, task_id: str, result: Optional[Dict[str, Any]] = None) -> Optional[TaskRecord]:
        """Mark task as successfully completed."""
        async with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                if task.status in (TaskStatus.ACTIVE, TaskStatus.RUNNING):
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = datetime.utcnow().isoformat()
                    task.result = result
                return task
        return None

    async def mark_stale_blocked(self, task_id: str) -> Optional[TaskRecord]:
        """Mark task as finished but blocked/fenced due to version obsolescence."""
        async with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                task.status = TaskStatus.STALE_BLOCKED
                task.completed_at = datetime.utcnow().isoformat()
                return task
        return None

    async def cancel_tasks_for_version(self, version: int) -> List[TaskRecord]:
        """
        Attempt to cancel all cancellable running tasks associated with the given version.
        Uncancellable tasks will remain running but will be fenced when they return.
        """
        cancelled_records: List[TaskRecord] = []
        async with self._lock:
            for tid, record in self._tasks.items():
                if record.version == version and record.status in (TaskStatus.ACTIVE, TaskStatus.RUNNING):
                    if not record.uncancellable:
                        record.status = TaskStatus.CANCELLED
                        record.cancelled_at = datetime.utcnow().isoformat()
                        cancelled_records.append(record)
                        
                        # Cancel asyncio task handle if present
                        if tid in self._asyncio_handles:
                            handle = self._asyncio_handles[tid]
                            if not handle.done():
                                handle.cancel()
                    else:
                        # Uncancellable task: cannot abort underlying execution, will be fenced on return
                        pass

        return cancelled_records

    def get_all_tasks(self) -> List[TaskRecord]:
        return list(self._tasks.values())

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        return self._tasks.get(task_id)

    def get_active_tasks_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status in (TaskStatus.ACTIVE, TaskStatus.RUNNING))

    def get_cancelled_tasks_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.CANCELLED)

    def get_stale_blocked_tasks_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.STALE_BLOCKED)
