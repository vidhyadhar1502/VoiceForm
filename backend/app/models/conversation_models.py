from enum import Enum
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
from datetime import datetime

class UserIntent(str, Enum):
    UPDATE_FIELD = "UPDATE_FIELD"
    SKIP_FIELD = "SKIP_FIELD"
    NAVIGATE_FIELD = "NAVIGATE_FIELD"
    CORRECT_FIELD = "CORRECT_FIELD"
    REQUEST_CLARIFICATION = "REQUEST_CLARIFICATION"
    STOP = "STOP"
    CONFIRM = "CONFIRM"

class StructuredAction(BaseModel):
    intent: UserIntent
    target_field: Optional[str] = None
    value: Optional[str] = None
    requires_validation: bool = False
    response_text: str

class EventLog(BaseModel):
    id: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    event_type: str
    interaction_version: int
    active_version: int
    message: str
    details: Optional[Dict[str, Any]] = None
    is_stale_blocked: bool = False

class SystemMetrics(BaseModel):
    interruptions_count: int = 0
    active_tasks_count: int = 0
    cancelled_tasks_count: int = 0
    stale_results_blocked_count: int = 0
    versions_created_count: int = 0
    interruption_to_audio_stop_time_ms: Optional[float] = None
