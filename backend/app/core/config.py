import os
from pydantic import BaseModel

class Settings(BaseModel):
    PROJECT_NAME: str = "VoiceForm"
    API_PREFIX: str = "/api"
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    RIME_API_KEY: str = os.getenv("RIME_API_KEY", "")
    RIME_MODEL: str = os.getenv("RIME_MODEL", "mist")
    RIME_VOICE: str = os.getenv("RIME_VOICE", "amber")
    RIME_ENDPOINT: str = os.getenv("RIME_ENDPOINT", "https://users.rime.ai/v1/rime-tts")
    DEFAULT_INITIAL_VERSION: int = 10
    DEFAULT_ARTIFICIAL_DELAY_SECONDS: float = 5.0

settings = Settings()
