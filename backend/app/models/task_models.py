from enum import Enum
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field
from datetime import datetime

class TaskStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    STALE_BLOCKED = "STALE_BLOCKED"
    FAILED = "FAILED"

class TaskRecord(BaseModel):
    task_id: str
    name: str
    target_field: Optional[str] = None
    version: int
    status: TaskStatus = TaskStatus.ACTIVE
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    cancelled_at: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    uncancellable: bool = False
