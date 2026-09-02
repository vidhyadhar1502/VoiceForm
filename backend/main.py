import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.services.interaction_version_manager import InteractionVersionManager
from backend.app.services.task_manager import TaskManager
from backend.app.services.stale_result_guard import StaleResultGuard
from backend.app.services.form_state_manager import FormStateManager
from backend.app.services.validation_service import ValidationService
from backend.app.services.stress_test_service import StressTestService
from backend.app.services.ai_service import AIService
from backend.app.services.action_validator import ActionValidator
from backend.app.services.conversation_service import ConversationService
from backend.app.services.speech_service import SpeechService
from backend.app.websocket.connection_manager import ConnectionManager
from backend.app.api.routes import create_api_router

# Core system singletons
version_manager = InteractionVersionManager(initial_version=settings.DEFAULT_INITIAL_VERSION)
task_manager = TaskManager()
stale_guard = StaleResultGuard(version_manager=version_manager, task_manager=task_manager)
form_state_manager = FormStateManager(stale_guard=stale_guard)
validation_service = ValidationService(default_delay=settings.DEFAULT_ARTIFICIAL_DELAY_SECONDS)
ws_manager = ConnectionManager()

# AI & Conversation services
ai_service = AIService(task_manager=task_manager)
action_validator = ActionValidator()

# Stress Test Service Singleton
stress_test_service = StressTestService(
    version_manager=version_manager,
    task_manager=task_manager,
    stale_guard=stale_guard,
    form_state_manager=form_state_manager,
    validation_service=validation_service,
    broadcast_fn=ws_manager.broadcast
)

# Speech Service Singleton
speech_service = SpeechService(
    version_manager=version_manager,
    task_manager=task_manager,
    stale_guard=stale_guard,
    broadcast_fn=ws_manager.broadcast,
    timeline_ref=stress_test_service.event_timeline
)

conversation_service = ConversationService(
    version_manager=version_manager,
    form_state_manager=form_state_manager,
    task_manager=task_manager,
    stale_guard=stale_guard,
    validation_service=validation_service,
    ai_service=ai_service,
    action_validator=action_validator,
    speech_service=speech_service,
    broadcast_fn=ws_manager.broadcast,
    timeline_ref=stress_test_service.event_timeline
)

# Wire invalidation listener: When new version is created, cancel tasks for old version
def _on_version_invalidated(old_version: int, new_version: int):
    asyncio.create_task(task_manager.cancel_tasks_for_version(old_version))
    asyncio.create_task(ws_manager.broadcast({
        "event": "interaction_invalidated",
        "invalidated_version": old_version,
        "active_version": new_version
    }))

version_manager.add_invalidation_listener(_on_version_invalidated)

# Wire stale result listener: Broadcast to WebSocket clients
def _on_stale_blocked(op_ver: int, active_ver: int, task_name: str, details: dict):
    asyncio.create_task(ws_manager.broadcast({
        "event": "stale_result_detected",
        "interaction_version": op_ver,
        "active_version": active_ver,
        "task": task_name,
        "details": details
    }))

stale_guard.register_stale_listener(_on_stale_blocked)

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API router with injected services
api_router = create_api_router(
    version_manager=version_manager,
    task_manager=task_manager,
    stale_guard=stale_guard,
    form_state_manager=form_state_manager,
    validation_service=validation_service,
    stress_test_service=stress_test_service,
    conversation_service=conversation_service,
    speech_service=speech_service,
    ws_manager=ws_manager
)
app.include_router(api_router, prefix=settings.API_PREFIX)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    # Send initial state snapshot on connect
    initial_snapshot = {
        "event": "session_snapshot",
        "active_version": version_manager.active_version,
        "form_state": form_state_manager.get_state().model_dump(),
        "tasks": [t.model_dump() for t in task_manager.get_all_tasks()],
        "stale_blocks_count": stale_guard.stale_blocks_count,
        "timeline": stress_test_service.event_timeline
    }
    await websocket.send_json(initial_snapshot)
    try:
        while True:
            data = await websocket.receive_text()
            # Can receive ping/pong or client messages
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
