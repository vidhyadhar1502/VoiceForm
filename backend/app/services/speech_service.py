import asyncio
import uuid
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from backend.app.services.speech_provider import SpeechProvider, RimeProvider, MockSpeechProvider
from backend.app.services.interaction_version_manager import InteractionVersionManager
from backend.app.services.task_manager import TaskManager
from backend.app.services.stale_result_guard import StaleResultGuard
from backend.app.core.config import settings

class SpeechService:
    """
    Orchestrates the version-tagged text-to-speech pipeline.
    Ensures that obsolete audio generated during or after an interruption is blocked
    before it can reach the playback queue or browser speaker.
    """
    def __init__(
        self,
        version_manager: InteractionVersionManager,
        task_manager: TaskManager,
        stale_guard: StaleResultGuard,
        provider: Optional[SpeechProvider] = None,
        broadcast_fn: Optional[Callable[[Dict[str, Any]], Any]] = None,
        timeline_ref: Optional[List[Dict[str, Any]]] = None
    ):
        self.version_manager = version_manager
        self.task_manager = task_manager
        self.stale_guard = stale_guard
        # Default to RimeProvider if API key present, otherwise MockSpeechProvider with fallback indicator
        if provider:
            self.provider = provider
        elif settings.RIME_API_KEY:
            self.provider = RimeProvider()
        else:
            self.provider = MockSpeechProvider()

        self.broadcast_fn = broadcast_fn
        self.timeline: List[Dict[str, Any]] = timeline_ref if timeline_ref is not None else []

        # Metrics
        self.total_tts_requests: int = 0
        self.cancelled_tts_requests: int = 0
        self.completed_tts_requests: int = 0
        self.stale_tts_results_blocked: int = 0
        self.audio_interruptions: int = 0
        self.audio_stop_requests: int = 0

    def set_provider(self, provider: SpeechProvider) -> None:
        """Switch active speech provider dynamically (e.g. for testing)."""
        self.provider = provider

    def get_provider_info(self) -> Dict[str, Any]:
        return {
            "provider_name": self.provider.provider_name,
            "is_fallback": self.provider.is_fallback,
            "rime_configured": bool(settings.RIME_API_KEY),
            "model": getattr(self.provider, "model", settings.RIME_MODEL),
            "voice": getattr(self.provider, "voice", settings.RIME_VOICE),
            "endpoint": getattr(self.provider, "endpoint", settings.RIME_ENDPOINT)
        }

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "total_tts_requests": self.total_tts_requests,
            "cancelled_tts_requests": self.cancelled_tts_requests,
            "completed_tts_requests": self.completed_tts_requests,
            "stale_tts_results_blocked": self.stale_tts_results_blocked,
            "audio_interruptions": self.audio_interruptions,
            "audio_stop_requests": self.audio_stop_requests
        }

    def reset(self) -> None:
        self.total_tts_requests = 0
        self.cancelled_tts_requests = 0
        self.completed_tts_requests = 0
        self.stale_tts_results_blocked = 0
        self.audio_interruptions = 0
        self.audio_stop_requests = 0

    async def _emit_event(
        self,
        event_type: str,
        interaction_version: int,
        active_version: int,
        message: str,
        task_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        is_stale_blocked: bool = False
    ) -> Dict[str, Any]:
        """Emits a version-tagged structured audio lifecycle event to timeline and WebSocket clients."""
        event = {
            "id": f"evt_{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "interaction_version": interaction_version,
            "active_version": active_version,
            "task_id": task_id,
            "message": message,
            "details": details or {},
            "is_stale_blocked": is_stale_blocked
        }
        self.timeline.append(event)
        if self.broadcast_fn:
            try:
                res = self.broadcast_fn({
                    "event": "structured_event",
                    "payload": event
                })
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
            except Exception:
                pass
        return event

    async def synthesize_response(
        self,
        text: str,
        interaction_version: int,
        uncancellable: bool = False
    ) -> Dict[str, Any]:
        """
        Executes the end-to-end version-guarded TTS synthesis:
        1. Checkpoint 1: Check active version before starting.
        2. Register TTS task in TaskManager.
        3. Emit TTS_REQUEST_STARTED & TTS_GENERATION_STARTED.
        4. Call SpeechProvider.
        5. Checkpoint 2: Check active version after generation.
        6. Checkpoint 3: Emit TTS_GENERATION_COMPLETED and broadcast audio payload.
        """
        self.total_tts_requests += 1
        active_ver = self.version_manager.active_version

        # Checkpoint 1: Version check before TTS task registration
        if interaction_version != active_ver:
            self.stale_tts_results_blocked += 1
            await self._emit_event(
                event_type="TTS_RESULT_BLOCKED_STALE",
                interaction_version=interaction_version,
                active_version=active_ver,
                message=f"Speech request for obsolete interaction v{interaction_version} blocked before start (Active: v{active_ver})",
                is_stale_blocked=True
            )
            return {
                "success": False,
                "is_stale": True,
                "interaction_version": interaction_version,
                "active_version": active_ver,
                "error": "Request version obsolete before start"
            }

        task_id = f"tts_task_{interaction_version}_{uuid.uuid4().hex[:6]}"
        curr_asyncio_task = asyncio.current_task()

        # Register task in TaskManager
        await self.task_manager.register_task(
            task_id=task_id,
            name=f"tts_{self.provider.provider_name}_{interaction_version}",
            version=interaction_version,
            target_field="speech_audio",
            payload={"text": text},
            uncancellable=uncancellable,
            asyncio_task=curr_asyncio_task
        )

        await self._emit_event(
            event_type="TTS_REQUEST_STARTED",
            interaction_version=interaction_version,
            active_version=active_ver,
            task_id=task_id,
            message=f"TTS request initiated for v{interaction_version} using {self.provider.provider_name}",
            details={"text": text, "provider": self.provider.provider_name}
        )

        await self._emit_event(
            event_type="TTS_GENERATION_STARTED",
            interaction_version=interaction_version,
            active_version=active_ver,
            task_id=task_id,
            message=f"Generating audio with {self.provider.provider_name} for v{interaction_version}",
            details={"provider": self.provider.provider_name}
        )

        try:
            audio_result = await self.provider.generate_speech(
                text=text,
                interaction_version=interaction_version,
                task_id=task_id
            )
        except asyncio.CancelledError:
            self.cancelled_tts_requests += 1
            active_now = self.version_manager.active_version
            await self._emit_event(
                event_type="TTS_RESULT_BLOCKED_STALE",
                interaction_version=interaction_version,
                active_version=active_now,
                task_id=task_id,
                message=f"TTS task {task_id} for v{interaction_version} cancelled on user interruption (Active: v{active_now})",
                details={"reason": "asyncio_cancelled"},
                is_stale_blocked=True
            )
            return {
                "success": False,
                "is_stale": True,
                "interaction_version": interaction_version,
                "active_version": active_now,
                "error": "TTS task cancelled"
            }
        except Exception as e:
            active_now = self.version_manager.active_version
            await self._emit_event(
                event_type="TTS_FAILED",
                interaction_version=interaction_version,
                active_version=active_now,
                task_id=task_id,
                message=f"TTS generation failed on {self.provider.provider_name}: {str(e)}",
                details={"error": str(e)}
            )
            return {
                "success": False,
                "is_stale": False,
                "interaction_version": interaction_version,
                "active_version": active_now,
                "error": str(e)
            }

        # Checkpoint 2: Version fence verification after Rime/Mock generation completes
        active_after_gen = self.version_manager.active_version
        if interaction_version != active_after_gen:
            self.stale_tts_results_blocked += 1
            await self._emit_event(
                event_type="TTS_RESULT_BLOCKED_STALE",
                interaction_version=interaction_version,
                active_version=active_after_gen,
                task_id=task_id,
                message=f"STALE AUDIO BLOCKED: Speech generated for obsolete interaction v{interaction_version} was rejected by fence (Active: v{active_after_gen})",
                details={"provider": self.provider.provider_name, "task_id": task_id},
                is_stale_blocked=True
            )
            await self.task_manager.mark_stale_blocked(task_id)
            return {
                "success": False,
                "is_stale": True,
                "interaction_version": interaction_version,
                "active_version": active_after_gen,
                "error": f"Stale TTS result for v{interaction_version} blocked"
            }

        # Checkpoint 3: Fresh audio accepted & broadcast to frontend
        self.completed_tts_requests += 1
        await self._emit_event(
            event_type="TTS_GENERATION_COMPLETED",
            interaction_version=interaction_version,
            active_version=active_after_gen,
            task_id=task_id,
            message=f"TTS generation completed successfully for v{interaction_version}",
            details={"byte_length": audio_result.get("byte_length", 0), "format": audio_result.get("format")}
        )

        await self._emit_event(
            event_type="TTS_RESULT_RETURNED",
            interaction_version=interaction_version,
            active_version=active_after_gen,
            task_id=task_id,
            message=f"Delivering fresh audio to playback queue for v{interaction_version}",
            details={"task_id": task_id}
        )

        # Broadcast audio payload to connected WebSockets
        if self.broadcast_fn:
            try:
                res = self.broadcast_fn({
                    "event": "audio_ready",
                    "interaction_version": interaction_version,
                    "active_version": active_after_gen,
                    "task_id": task_id,
                    "audio_url": audio_result.get("audio_url"),
                    "audio_base64": audio_result.get("audio_base64"),
                    "format": audio_result.get("format"),
                    "provider": self.provider.provider_name
                })
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
            except Exception:
                pass

        return {
            "success": True,
            "is_stale": False,
            "interaction_version": interaction_version,
            "active_version": active_after_gen,
            "task_id": task_id,
            "audio_result": audio_result
        }

    async def record_audio_playback_event(
        self,
        event_type: str,
        interaction_version: int,
        task_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Records client-reported playback lifecycle events (e.g. AUDIO_PLAYBACK_STARTED, AUDIO_PLAYBACK_STOPPED)."""
        active_ver = self.version_manager.active_version
        if event_type == "AUDIO_PLAYBACK_STOPPED":
            self.audio_stop_requests += 1
        elif event_type == "AUDIO_INTERRUPTION":
            self.audio_interruptions += 1

        msg = f"Playback event: {event_type} for v{interaction_version}"
        if event_type == "AUDIO_PLAYBACK_STARTED":
            msg = f"Audio playback started for v{interaction_version}"
        elif event_type == "AUDIO_PLAYBACK_STOPPED":
            msg = f"Audio playback stopped for v{interaction_version} (Active: v{active_ver})"
        elif event_type == "AUDIO_QUEUE_CLEARED":
            msg = f"Obsolete audio queue cleared on new interaction v{active_ver}"
        elif event_type == "AUDIO_PLAYBACK_COMPLETED":
            msg = f"Audio playback completed for v{interaction_version}"

        await self._emit_event(
            event_type=event_type,
            interaction_version=interaction_version,
            active_version=active_ver,
            task_id=task_id,
            message=msg,
            details=details
        )

    def reset(self) -> None:
        """Resets speech service metrics."""
        self.total_tts_requests = 0
        self.cancelled_tts_requests = 0
        self.completed_tts_requests = 0
        self.stale_tts_results_blocked = 0
        self.audio_interruptions = 0
        self.audio_stop_requests = 0
