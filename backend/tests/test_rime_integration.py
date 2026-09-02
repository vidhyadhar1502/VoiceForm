import os
import pytest
from backend.app.core.config import settings
from backend.app.services.speech_provider import RimeProvider

@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("RIME_API_KEY"), reason="RIME_API_KEY not configured. Skipping live Rime integration test.")
async def test_real_rime_speech_generation():
    """
    Live integration test against the real Rime REST API.
    Runs only when RIME_API_KEY is supplied.
    """
    api_key = os.getenv("RIME_API_KEY")
    assert api_key, "RIME_API_KEY must be present"

    provider = RimeProvider(
        api_key=api_key,
        model=settings.RIME_MODEL,
        voice=settings.RIME_VOICE,
        endpoint=settings.RIME_ENDPOINT,
        timeout_seconds=15.0
    )

    res = await provider.generate_speech(
        text="VoiceForm real Rime integration test.",
        interaction_version=99
    )

    assert res["success"] is True
    assert res["byte_length"] > 0
    assert res["format"] == "audio/mp3"
    assert res["model"] == settings.RIME_MODEL
    assert res["voice"] == settings.RIME_VOICE
    assert res["interaction_version"] == 99
    assert res["audio_base64"] is not None
