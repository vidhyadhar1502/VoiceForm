from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
from pydantic import BaseModel

from backend.app.models.form_models import FormState
from backend.app.models.task_models import TaskRecord
from backend.app.services.interaction_version_manager import InteractionVersionManager
from backend.app.services.form_state_manager import FormStateManager
from backend.app.services.stale_result_guard import StaleResultGuard
from backend.app.services.task_manager import TaskManager
from backend.app.services.validation_service import ValidationService

api_router = APIRouter()

# Service dependencies will be injected from main.py app state or helper getters
class UpdateFieldRequest(BaseModel):
    field_name: str
    value: str
    version: int

class SetDelayRequest(BaseModel):
    delay_seconds: float

class InterruptionRequest(BaseModel):
    reason: str = "User Interruption"

@api_router.get("/health")
async def health_check():
    return {"status": "ok", "service": "VoiceForm Backend"}
