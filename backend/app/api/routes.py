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
from backend.app.services.speech_service import SpeechService
from backend.app.services.speech_provider import RimeProvider, MockSpeechProvider
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

class SpeechGenerateRequest(BaseModel):
    text: str
    version: Optional[int] = None
    uncancellable: bool = False

class AudioPlaybackEventRequest(BaseModel):
    event_type: str
    interaction_version: int
    task_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class SwitchSpeechProviderRequest(BaseModel):
    provider: str  # "rime" | "mock"
    artificial_delay: float = 0.0
    should_fail: bool = False

class AudioRaceTestRequest(BaseModel):
    scenario: str = "MODE_A"  # "MODE_A" | "MODE_B" | "MODE_C"

def create_api_router(
    version_manager: InteractionVersionManager,
    task_manager: TaskManager,
    stale_guard: StaleResultGuard,
    form_state_manager: FormStateManager,
    validation_service: ValidationService,
    stress_test_service: StressTestService,
    conversation_service: ConversationService,
    speech_service: SpeechService,
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

    @router.get("/speech/status")
    async def get_speech_status():
        """Returns provider information, active version, and audio metrics."""
        return {
            "provider_info": speech_service.get_provider_info(),
            "metrics": speech_service.get_metrics(),
            "active_version": version_manager.active_version
        }

    @router.post("/speech/provider")
    async def switch_speech_provider(req: SwitchSpeechProviderRequest):
        """Switches between Rime and Mock speech providers with test parameters."""
        if req.provider.lower() == "rime":
            provider = RimeProvider()
        else:
            provider = MockSpeechProvider(
                artificial_delay=req.artificial_delay,
                should_fail=req.should_fail
            )
        speech_service.set_provider(provider)
        return {
            "status": "provider_switched",
            "provider_info": speech_service.get_provider_info()
        }

    @router.post("/speech/generate")
    async def generate_speech_audio(req: SpeechGenerateRequest):
        """Triggers speech synthesis for a given response text under version fencing."""
        ver = req.version if req.version is not None else version_manager.active_version
        result = await speech_service.synthesize_response(
            text=req.text,
            interaction_version=ver,
            uncancellable=req.uncancellable
        )
        return result

    @router.post("/speech/playback-event")
    async def log_playback_event(req: AudioPlaybackEventRequest):
        """Receives browser audio playback lifecycle events and records them in the timeline."""
        await speech_service.record_audio_playback_event(
            event_type=req.event_type,
            interaction_version=req.interaction_version,
            task_id=req.task_id,
            details=req.details
        )
        return {"status": "recorded"}

    @router.post("/demo/audio-race-test")
    async def run_audio_race_test(req: AudioRaceTestRequest):
        """
        Runs automated race condition simulations for speech pipeline:
        - MODE_A: Stale TTS Generation (v40 2s delay interrupted by v41 -> v40 blocked as stale).
        - MODE_B: Stop Current Playback (v50 playing interrupted by v51 -> v50 playback stopped, queue cleared).
        - MODE_C: Multiple Queued Responses (v60, v61, v62 fired rapidly -> only v62 eligible for playback).
        """
        import asyncio
        original_provider = speech_service.provider

        try:
            if req.scenario == "MODE_A":
                # Mode A: Stale TTS Generation
                # 1. Reset to v40
                version_manager.reset(initial_version=40)
                mock_provider = MockSpeechProvider(artificial_delay=2.0)
                speech_service.set_provider(mock_provider)

                # 2. Launch TTS for v40 (uncancellable to simulate slow network payload returning)
                task_v40 = asyncio.create_task(
                    speech_service.synthesize_response(
                        text="I have updated your address to Chennai.",
                        interaction_version=40,
                        uncancellable=True
                    )
                )

                # 3. Interrupt after 0.3s with v41
                await asyncio.sleep(0.3)
                v41 = await version_manager.create_new_version(reason="User voice interruption: 'Actually no, postal code is 600028'")
                
                # 4. Await v40 completion
                v40_result = await task_v40

                return {
                    "scenario": "MODE_A",
                    "description": "Stale TTS Generation Interruption",
                    "v40_result": v40_result,
                    "initial_version": 40,
                    "new_version": v41,
                    "active_version": version_manager.active_version,
                    "v40_blocked_as_stale": v40_result.get("is_stale", False),
                    "timeline": list(stress_test_service.event_timeline)
                }

            elif req.scenario == "MODE_B":
                # Mode B: Stop Current Playback
                version_manager.reset(initial_version=50)
                mock_provider = MockSpeechProvider(artificial_delay=0.0)
                speech_service.set_provider(mock_provider)

                # Synthesize v50 audio
                v50_result = await speech_service.synthesize_response(
                    text="Your date of birth has been set.",
                    interaction_version=50
                )
                
                # Simulate playback start
                await speech_service.record_audio_playback_event(
                    event_type="AUDIO_PLAYBACK_STARTED",
                    interaction_version=50,
                    task_id=v50_result.get("task_id")
                )

                # User interrupts with v51
                await asyncio.sleep(0.2)
                v51 = await version_manager.create_new_version(reason="User voice interruption: 'Wait, correct date is 1992'")

                # Playback stopped event
                await speech_service.record_audio_playback_event(
                    event_type="AUDIO_PLAYBACK_STOPPED",
                    interaction_version=50,
                    task_id=v50_result.get("task_id"),
                    details={"reason": "interaction_invalidated"}
                )

                return {
                    "scenario": "MODE_B",
                    "description": "Stop Current Playback on Interruption",
                    "v50_result": v50_result,
                    "initial_version": 50,
                    "new_version": v51,
                    "active_version": version_manager.active_version,
                    "timeline": list(stress_test_service.event_timeline)
                }

            elif req.scenario == "MODE_C":
                # Mode C: Multiple Queued Responses
                version_manager.reset(initial_version=60)
                mock_provider = MockSpeechProvider(artificial_delay=0.1)
                speech_service.set_provider(mock_provider)

                t1 = asyncio.create_task(speech_service.synthesize_response("Message 60", interaction_version=60, uncancellable=True))
                await asyncio.sleep(0.05)
                v61 = await version_manager.create_new_version(reason="Input 61")
                t2 = asyncio.create_task(speech_service.synthesize_response("Message 61", interaction_version=61, uncancellable=True))
                await asyncio.sleep(0.05)
                v62 = await version_manager.create_new_version(reason="Input 62")
                t3 = asyncio.create_task(speech_service.synthesize_response("Message 62", interaction_version=62, uncancellable=True))

                r1, r2, r3 = await asyncio.gather(t1, t2, t3)

                return {
                    "scenario": "MODE_C",
                    "description": "Multiple Rapid Interrupted Requests",
                    "v60_is_stale": r1.get("is_stale"),
                    "v61_is_stale": r2.get("is_stale"),
                    "v62_is_stale": r3.get("is_stale"),
                    "v60_success": r1.get("success"),
                    "v61_success": r2.get("success"),
                    "v62_success": r3.get("success"),
                    "active_version": version_manager.active_version,
                    "timeline": list(stress_test_service.event_timeline)
                }
            else:
                raise HTTPException(status_code=400, detail=f"Unknown scenario {req.scenario}")
        finally:
            speech_service.set_provider(original_provider)

    @router.get("/demo/timeline")
    async def get_timeline():
        return {
            "timeline": list(stress_test_service.event_timeline),
            "count": len(stress_test_service.event_timeline)
        }

    return router
