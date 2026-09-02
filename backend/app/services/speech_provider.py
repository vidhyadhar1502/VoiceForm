import abc
import asyncio
import base64
import struct
from typing import Dict, Any, Optional
import httpx
from backend.app.core.config import settings

def generate_minimal_valid_wav_base64(duration_seconds: float = 0.5, sample_rate: int = 8000) -> str:
    """
    Generates a valid, minimal uncompressed 8-bit mono PCM WAV audio file in base64.
    Ensures browser Audio elements and test suites can decode and play without codec errors.
    """
    num_samples = int(duration_seconds * sample_rate)
    # Generate a soft 440Hz sine wave tone or silence
    data = bytearray()
    for i in range(num_samples):
        # Soft sine wave oscillation between 100 and 156
        import math
        val = int(128 + 28 * math.sin(2 * math.pi * 440 * (i / sample_rate)))
        data.append(val & 0xFF)

    # 44-byte RIFF WAV Header
    header = bytearray()
    header.extend(b'RIFF')
    header.extend(struct.pack('<I', 36 + len(data)))  # File size - 8
    header.extend(b'WAVE')
    header.extend(b'fmt ')
    header.extend(struct.pack('<I', 16))              # Subchunk1Size (16 for PCM)
    header.extend(struct.pack('<H', 1))               # AudioFormat (1 = PCM)
    header.extend(struct.pack('<H', 1))               # NumChannels (1 = Mono)
    header.extend(struct.pack('<I', sample_rate))     # SampleRate
    header.extend(struct.pack('<I', sample_rate))     # ByteRate (SampleRate * NumChannels * BitsPerSample/8)
    header.extend(struct.pack('<H', 1))               # BlockAlign (NumChannels * BitsPerSample/8)
    header.extend(struct.pack('<H', 8))               # BitsPerSample
    header.extend(b'data')
    header.extend(struct.pack('<I', len(data)))        # Subchunk2Size

    wav_bytes = bytes(header + data)
    return base64.b64encode(wav_bytes).decode('utf-8')


class SpeechProvider(abc.ABC):
    """
    Abstract interface for speech synthesis providers.
    """
    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def is_fallback(self) -> bool:
        pass

    @abc.abstractmethod
    async def generate_speech(
        self,
        text: str,
        interaction_version: int,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates audio for the given text and interaction version.
        Returns a dictionary with audio data, format, and metadata.
        """
        pass


class RimeProvider(SpeechProvider):
    """
    Primary production speech provider communicating with Rime REST API.
    Does not mutate form state or decide interaction versions.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        voice: Optional[str] = None,
        endpoint: Optional[str] = None,
        timeout_seconds: float = 10.0
    ):
        self.api_key = api_key or settings.RIME_API_KEY
        self.model = model or settings.RIME_MODEL
        self.voice = voice or settings.RIME_VOICE
        self.endpoint = endpoint or settings.RIME_ENDPOINT
        self.timeout_seconds = timeout_seconds

    @property
    def provider_name(self) -> str:
        return "Rime"

    @property
    def is_fallback(self) -> bool:
        return False

    async def generate_speech(
        self,
        text: str,
        interaction_version: int,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes text using Rime TTS HTTP endpoint.
        """
        if not self.api_key:
            raise ValueError(
                "RIME_API_KEY is not configured. Please supply a valid Rime API key in .env or switch to MockSpeechProvider."
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "audio/mp3",
            "Content-Type": "application/json"
        }

        payload = {
            "text": text,
            "speaker": self.voice,
            "modelId": self.model
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(self.endpoint, headers=headers, json=payload)
            if response.status_code != 200:
                error_body = response.text
                raise RuntimeError(
                    f"Rime API returned HTTP {response.status_code}: {error_body}"
                )

            audio_bytes = response.content
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

            return {
                "success": True,
                "provider": "Rime",
                "audio_base64": audio_base64,
                "audio_url": f"data:audio/mp3;base64,{audio_base64}",
                "format": "audio/mp3",
                "interaction_version": interaction_version,
                "task_id": task_id,
                "byte_length": len(audio_bytes),
                "model": self.model,
                "voice": self.voice
            }


class MockSpeechProvider(SpeechProvider):
    """
    Deterministic speech provider for automated unit testing and offline demo execution.
    Supports artificial delay, simulated cancellation, and forced failures.
    """
    def __init__(
        self,
        artificial_delay: float = 0.0,
        should_fail: bool = False,
        failure_message: str = "Simulated MockSpeechProvider failure",
        mock_audio_data: Optional[str] = None
    ):
        self.artificial_delay = artificial_delay
        self.should_fail = should_fail
        self.failure_message = failure_message
        self._custom_audio_data = mock_audio_data
        self._forced_responses: Dict[str, Dict[str, Any]] = {}

    @property
    def provider_name(self) -> str:
        return "Mock (Deterministic)"

    @property
    def is_fallback(self) -> bool:
        return True

    def set_forced_response(self, text: str, response: Dict[str, Any]) -> None:
        self._forced_responses[text] = response

    async def generate_speech(
        self,
        text: str,
        interaction_version: int,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes mock audio with configurable delay.
        """
        if self.artificial_delay > 0:
            await asyncio.sleep(self.artificial_delay)

        if self.should_fail:
            raise RuntimeError(self.failure_message)

        if text in self._forced_responses:
            res = dict(self._forced_responses[text])
            res["interaction_version"] = interaction_version
            res["task_id"] = task_id
            return res

        audio_b64 = self._custom_audio_data or generate_minimal_valid_wav_base64(duration_seconds=0.4)

        return {
            "success": True,
            "provider": "Mock (Deterministic)",
            "audio_base64": audio_b64,
            "audio_url": f"data:audio/wav;base64,{audio_b64}",
            "format": "audio/wav",
            "interaction_version": interaction_version,
            "task_id": task_id,
            "byte_length": len(audio_b64),
            "model": "mock-tts-v1",
            "voice": "mock-voice"
        }
