import asyncio
import uuid
from typing import Dict, Any, Optional
from backend.app.services.ai_provider import AIProvider, GeminiProvider, MockAIProvider
from backend.app.services.task_manager import TaskManager
from backend.app.core.config import settings

class AIService:
    """
    AI Service coordinating LLM interpretation with version-tagging and TaskManager registry.
    """
    def __init__(self, provider: Optional[AIProvider] = None, task_manager: Optional[TaskManager] = None):
        self.provider: AIProvider = provider or GeminiProvider(
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL
        )
        self.task_manager: Optional[TaskManager] = task_manager

    def set_provider(self, provider: AIProvider) -> None:
        """Allow switching provider (e.g. for deterministic unit testing with MockAIProvider)."""
        self.provider = provider

    async def interpret_input(
        self,
        text: str,
        context: Dict[str, Any],
        interaction_version: int,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Registers an async task with TaskManager, calls the configured AIProvider,
        and returns the raw structured action output.
        """
        tid = task_id or f"ai_task_{uuid.uuid4().hex[:8]}"

        # Register task in TaskManager if available
        if self.task_manager:
            await self.task_manager.register_task(
                task_id=tid,
                name="gemini_interpret_input",
                version=interaction_version,
                target_field=context.get("active_field_key"),
                payload={"text": text, "context": context},
                uncancellable=False
            )

        try:
            # Call AI Provider
            result = await self.provider.interpret_user_input(
                text=text,
                context=context,
                interaction_version=interaction_version
            )
            return result
        except asyncio.CancelledError:
            # Task was cancelled due to version invalidation
            raise
        except Exception as e:
            return {
                "action": "REQUEST_CLARIFICATION",
                "target_field": None,
                "value": None,
                "requires_validation": False,
                "response_text": f"I ran into an issue interpreting that. Could you please rephrase?",
                "error": str(e)
            }
