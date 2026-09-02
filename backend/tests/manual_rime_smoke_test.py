import asyncio
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.core.config import settings
from backend.app.services.speech_provider import RimeProvider

async def run_rime_smoke_test():
    api_key = os.getenv("RIME_API_KEY", settings.RIME_API_KEY)
    if not api_key:
        print("=" * 60)
        print("RIME_SMOKE_TEST_SKIPPED: RIME_API_KEY environment variable is not configured.")
        print("To run the real Rime smoke test:")
        print("  export RIME_API_KEY=\"your_api_key_here\"")
        print("  python backend/tests/manual_rime_smoke_test.py")
        print("=" * 60)
        return False

    print("=" * 60)
    print("RUNNING REAL RIME INTEGRATION SMOKE TEST")
    print("=" * 60)

    provider = RimeProvider(
        api_key=api_key,
        model=settings.RIME_MODEL,
        voice=settings.RIME_VOICE,
        endpoint=settings.RIME_ENDPOINT,
        timeout_seconds=15.0
    )

    test_text = "VoiceForm live test: Rime text to speech synthesis."
    test_version = 101

    try:
        result = await provider.generate_speech(
            text=test_text,
            interaction_version=test_version,
            task_id="smoke_test_task_001"
        )

        success = result.get("success", False)
        audio_bytes_len = result.get("byte_length", 0)
        audio_format = result.get("format", "unknown")
        model = result.get("model", provider.model)
        voice = result.get("voice", provider.voice)
        endpoint = provider.endpoint

        if not success or audio_bytes_len <= 0:
            print("RIME_SMOKE_TEST_FAILED: No audio bytes returned.")
            return False

        print("\nRIME_SMOKE_TEST_SUCCESS")
        print(f"Model: {model}")
        print(f"Voice: {voice}")
        print(f"Endpoint: {endpoint}")
        print(f"Audio bytes: {audio_bytes_len}")
        print(f"Format: {audio_format}")
        print("Interaction Version Tag:", result.get("interaction_version"))
        print("=" * 60)
        return True

    except Exception as e:
        print("\nRIME_SMOKE_TEST_ERROR")
        print(f"Error during Rime synthesis: {str(e)}")
        print(f"Model: {provider.model}")
        print(f"Voice: {provider.voice}")
        print(f"Endpoint: {provider.endpoint}")
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = asyncio.run(run_rime_smoke_test())
    sys.exit(0 if success or not os.getenv("RIME_API_KEY") else 1)
