from enum import Enum
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
from datetime import datetime

class UserIntent(str, Enum):
    UPDATE_FIELD = "UPDATE_FIELD"
    CORRECT_FIELD = "CORRECT_FIELD"
    SKIP_FIELD = "SKIP_FIELD"
    NAVIGATE_FIELD = "NAVIGATE_FIELD"
    REQUEST_CLARIFICATION = "REQUEST_CLARIFICATION"
    GET_FORM_SUMMARY = "GET_FORM_SUMMARY"
    STOP = "STOP"
    CONFIRM = "CONFIRM"

class StructuredAction(BaseModel):
    action: UserIntent = Field(default=UserIntent.UPDATE_FIELD)
    intent: Optional[UserIntent] = None
    target_field: Optional[str] = None
    value: Optional[str] = None
    requires_validation: bool = False
    response_text: str = ""
    is_valid: bool = True
    validation_error: Optional[str] = None

    def model_post_init(self, __context: Any) -> None:
        if self.intent is None:
            self.intent = self.action
        elif self.action is None:
            self.action = self.intent

class ConversationMessage(BaseModel):
    id: str
    role: str  # "user" | "assistant" | "system"
    text: str
    interaction_version: int
    active_version: int
    structured_action: Optional[StructuredAction] = None
    is_stale: bool = False
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

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
