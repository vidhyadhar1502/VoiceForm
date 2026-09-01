from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel

from backend.app.models.form_models import FormState
from backend.app.models.task_models import TaskRecord
from backend.app.services.interaction_version_manager import InteractionVersionManager
from backend.app.services.form_state_manager import FormStateManager
from backend.app.services.stale_result_guard import StaleResultGuard
from backend.app.services.task_manager import TaskManager
from backend.app.services.validation_service import ValidationService
from backend.app.services.stress_test_service import StressTestService
from backend.app.services.conversation_service import ConversationService
from backend.app.websocket.connection_manager import ConnectionManager

class StressTestRequest(BaseModel):
    mode: str = "uncancellable"  # "cancellable" | "uncancellable"
    old_postal_code: str = "600001"
    new_postal_code: str = "600028"
    validation_delay_seconds: float = 3.0
    interrupt_after_seconds: float = 1.0

class ConversationInputRequest(BaseModel):
    text: str

class UpdateFieldRequest(BaseModel):
    field_name: str
    value: str
    version: int

class ResetRequest(BaseModel):
    initial_version: int = 10

def create_api_router(
    version_manager: InteractionVersionManager,
    task_manager: TaskManager,
    stale_guard: StaleResultGuard,
    form_state_manager: FormStateManager,
    validation_service: ValidationService,
    stress_test_service: StressTestService,
    conversation_service: ConversationService,
    ws_manager: ConnectionManager
) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health_check():
        return {
            "status": "ok",
            "service": "VoiceForm Backend",
            "active_version": version_manager.active_version,
            "stale_blocks_count": stale_guard.stale_blocks_count
        }

    @router.post("/conversation/input")
    async def process_conversation_input(req: ConversationInputRequest):
        """
        Processes natural language instructions through Gemini AI interpretation,
        ActionValidator schema verification, version-fencing, and authoritative FormState updates.
        """
        try:
            result = await conversation_service.process_user_input(req.text)
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/conversation/history")
    async def get_conversation_history():
        """Returns the conversation message history with interaction versions and structured actions."""
        return {
            "messages": conversation_service.get_history(),
            "active_version": version_manager.active_version
        }

    @router.post("/conversation/reset")
    async def reset_conversation():
        """Clears conversation history and resets form state."""
        conversation_service.reset()
        form_state_manager.reset()
        version_manager.reset(initial_version=10)
        stale_guard.reset()
        task_manager.reset()
        stress_test_service.event_timeline.clear()
        
        await ws_manager.broadcast({
            "event": "conversation_reset",
            "active_version": version_manager.active_version,
            "form_state": form_state_manager.get_state().model_dump()
        })
        return {
            "status": "reset_success",
            "active_version": version_manager.active_version,
            "form_state": form_state_manager.get_state().model_dump()
        }

    @router.post("/demo/stress-test")
    async def run_stress_test(req: StressTestRequest):
        """
        Runs a deterministic stress test demonstrating that stale asynchronous results
        cannot overwrite newer state under rapid user interruptions.
        """
        try:
            result = await stress_test_service.run_stress_test(
                mode=req.mode,
                old_postal_code=req.old_postal_code,
                new_postal_code=req.new_postal_code,
                validation_delay_seconds=req.validation_delay_seconds,
                interrupt_after_seconds=req.interrupt_after_seconds,
                reset_before_run=True
            )
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/demo/state")
    async def get_system_state():
        """Returns the current full snapshot of the system state."""
        return {
            "active_version": version_manager.active_version,
            "form_state": form_state_manager.get_state().model_dump(),
            "tasks": [t.model_dump() for t in task_manager.get_all_tasks()],
            "stale_results_blocked": stale_guard.stale_blocks_count,
            "cancelled_tasks_count": task_manager.get_cancelled_tasks_count(),
            "active_tasks_count": task_manager.get_active_tasks_count(),
            "blocked_events": stale_guard.get_blocked_events(),
            "timeline": list(stress_test_service.event_timeline)
        }

    @router.post("/demo/reset")
    async def reset_session(req: Optional[ResetRequest] = None):
        """Resets all system state, versions, and timelines cleanly."""
        init_ver = req.initial_version if req else 10
        stress_test_service.reset_session(initial_version=init_ver)
        conversation_service.reset()
        await ws_manager.broadcast({
            "event": "session_reset",
            "active_version": version_manager.active_version,
            "form_state": form_state_manager.get_state().model_dump(),
            "stale_blocks_count": 0
        })
        return {
            "status": "reset_complete",
            "active_version": version_manager.active_version,
            "form_state": form_state_manager.get_state().model_dump()
        }

    @router.get("/demo/timeline")
    async def get_timeline():
        return {
            "timeline": list(stress_test_service.event_timeline),
            "count": len(stress_test_service.event_timeline)
        }

    return router
