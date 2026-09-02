from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
import asyncio

class SpeechRecognitionProvider(ABC):
    """
    Abstract interface for Speech-to-Text Providers.
    Responsible solely for:
    - Capturing speech input
    - Producing transcript text
    - Reporting recognition state and errors
    
    MUST NOT:
    - Directly modify FormState
    - Directly call AI/Gemini
    - Directly alter interaction versions
    """
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    async def recognize(self, **kwargs) -> Dict[str, Any]:
        pass

class MockSpeechRecognitionProvider(SpeechRecognitionProvider):
    """
    Deterministic mock speech recognition provider for tests and simulation.
    """
    def __init__(
        self,
        final_transcript: str = "My postal code is 600001",
        interim_steps: Optional[List[str]] = None,
        artificial_delay: float = 0.05,
        should_fail: bool = False,
        permission_denied: bool = False,
        error_message: Optional[str] = None
    ):
        self._final_transcript = final_transcript
        self._interim_steps = interim_steps or ["My postal", "My postal code", "My postal code is 600001"]
        self._artificial_delay = artificial_delay
        self._should_fail = should_fail
        self._permission_denied = permission_denied
        self._error_message = error_message or "Speech recognition failed"

    @property
    def provider_name(self) -> str:
        return "MockSpeechRecognition"

    async def recognize(
        self,
        interim_callback: Optional[Callable[[str], Any]] = None,
        override_transcript: Optional[str] = None
    ) -> Dict[str, Any]:
        if self._permission_denied:
            return {
                "success": False,
                "error": "Microphone permission denied",
                "is_permission_denied": True,
                "transcript": ""
            }

        if self._should_fail:
            return {
                "success": False,
                "error": self._error_message,
                "is_permission_denied": False,
                "transcript": ""
            }

        # Emit interim steps if provided
        for step in self._interim_steps:
            if self._artificial_delay > 0:
                await asyncio.sleep(self._artificial_delay)
            if interim_callback:
                res = interim_callback(step)
                if asyncio.iscoroutine(res):
                    await res

        transcript = override_transcript if override_transcript is not None else self._final_transcript
        return {
            "success": True,
            "transcript": transcript,
            "is_final": True,
            "confidence": 0.98
        }
