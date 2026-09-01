import pytest
import asyncio
from typing import Dict, Any

from backend.app.models.conversation_models import UserIntent, StructuredAction
from backend.app.models.form_models import FieldStatus, ValidationStatus
from backend.app.services.interaction_version_manager import InteractionVersionManager
from backend.app.services.form_state_manager import FormStateManager
from backend.app.services.task_manager import TaskManager
from backend.app.services.stale_result_guard import StaleResultGuard
from backend.app.services.validation_service import ValidationService
from backend.app.services.ai_provider import MockAIProvider, RuleBasedFallbackProvider
from backend.app.services.ai_service import AIService
from backend.app.services.action_validator import ActionValidator
from backend.app.services.conversation_service import ConversationService

@pytest.fixture
def test_setup():
    version_mgr = InteractionVersionManager(initial_version=10)
    task_mgr = TaskManager()
    stale_guard = StaleResultGuard(version_manager=version_mgr, task_manager=task_mgr)
    form_mgr = FormStateManager(stale_guard=stale_guard)
    val_service = ValidationService(default_delay=0.1)
    mock_ai_provider = MockAIProvider(artificial_delay=0.0)
    ai_service = AIService(provider=mock_ai_provider, task_manager=task_mgr)
    action_validator = ActionValidator()
    timeline = []

    # Invalidation listener for version manager
    def _on_invalidated(old_ver, new_ver):
        asyncio.create_task(task_mgr.cancel_tasks_for_version(old_ver))
    version_mgr.add_invalidation_listener(_on_invalidated)

    conv_service = ConversationService(
        version_manager=version_mgr,
        form_state_manager=form_mgr,
        task_manager=task_mgr,
        stale_guard=stale_guard,
        validation_service=val_service,
        ai_service=ai_service,
        action_validator=action_validator,
        timeline_ref=timeline
    )

    return {
        "version_mgr": version_mgr,
        "task_mgr": task_mgr,
        "stale_guard": stale_guard,
        "form_mgr": form_mgr,
        "val_service": val_service,
        "mock_ai_provider": mock_ai_provider,
        "ai_service": ai_service,
        "action_validator": action_validator,
        "conv_service": conv_service,
        "timeline": timeline
    }

# 1. UPDATE_FIELD action
@pytest.mark.asyncio
async def test_update_field_action(test_setup):
    conv = test_setup["conv_service"]
    form_mgr = test_setup["form_mgr"]

    res = await conv.process_user_input("My name is Vidhyadhar S.")
    assert res["success"] is True
    assert res["action"]["action"] == "UPDATE_FIELD"
    assert res["action"]["target_field"] == "full_name"
    assert res["action"]["value"] == "Vidhyadhar S"

    state = form_mgr.get_state()
    assert state.fields["full_name"].value == "Vidhyadhar S"
    assert state.fields["full_name"].status == FieldStatus.CONFIRMED

# 2. CORRECT_FIELD action
@pytest.mark.asyncio
async def test_correct_field_action(test_setup):
    conv = test_setup["conv_service"]
    form_mgr = test_setup["form_mgr"]

    # Initial value
    await conv.process_user_input("I work as a Junior Developer")
    assert form_mgr.get_state().fields["occupation"].value == "Junior Developer"

    # Correction
    res = await conv.process_user_input("Actually, change my occupation to Software Developer")
    assert res["success"] is True
    assert res["action"]["action"] == "CORRECT_FIELD"
    assert res["action"]["target_field"] == "occupation"
    assert res["action"]["value"] == "Software Developer"

    state = form_mgr.get_state()
    assert state.fields["occupation"].value == "Software Developer"

# 3. SKIP_FIELD action
@pytest.mark.asyncio
async def test_skip_field_action(test_setup):
    conv = test_setup["conv_service"]
    form_mgr = test_setup["form_mgr"]

    res = await conv.process_user_input("Skip the address for now.")
    assert res["success"] is True
    assert res["action"]["action"] == "SKIP_FIELD"
    assert res["action"]["target_field"] == "address"

    state = form_mgr.get_state()
    assert state.fields["address"].status == FieldStatus.SKIPPED

# 4. NAVIGATE_FIELD action
@pytest.mark.asyncio
async def test_navigate_field_action(test_setup):
    conv = test_setup["conv_service"]
    form_mgr = test_setup["form_mgr"]

    res = await conv.process_user_input("Go back to my phone number.")
    assert res["success"] is True
    assert res["action"]["action"] == "NAVIGATE_FIELD"
    assert res["action"]["target_field"] == "phone_number"

    state = form_mgr.get_state()
    assert state.active_field_key == "phone_number"

# 5. Unknown field rejection
@pytest.mark.asyncio
async def test_unknown_field_rejection(test_setup):
    conv = test_setup["conv_service"]
    form_mgr = test_setup["form_mgr"]
    mock_ai = test_setup["mock_ai_provider"]

    # Force AI to return an unknown field
    mock_ai.set_forced_response("My favorite superhero is Batman", {
        "action": "UPDATE_FIELD",
        "target_field": "superhero_name",
        "value": "Batman",
        "requires_validation": False,
        "response_text": "Saved superhero"
    })

    res = await conv.process_user_input("My favorite superhero is Batman")
    assert res["action"]["action"] == "REQUEST_CLARIFICATION"
    assert res["action"]["is_valid"] is False

    # State must not be modified
    state = form_mgr.get_state()
    assert "superhero_name" not in state.fields

# 6. Invalid Gemini structured output rejection
@pytest.mark.asyncio
async def test_invalid_gemini_structured_output_rejection(test_setup):
    conv = test_setup["conv_service"]
    form_mgr = test_setup["form_mgr"]
    mock_ai = test_setup["mock_ai_provider"]

    # Force malformed action
    mock_ai.set_forced_response("Malformed json", {
        "action": "NON_EXISTENT_INTENT_XYZ",
        "target_field": "full_name",
        "value": "Test",
        "requires_validation": False
    })

    res = await conv.process_user_input("Malformed json")
    assert res["action"]["action"] == "REQUEST_CLARIFICATION"
    assert res["action"]["is_valid"] is False

# 7. GET_FORM_SUMMARY generated from authoritative form state
@pytest.mark.asyncio
async def test_get_form_summary_from_authoritative_state(test_setup):
    conv = test_setup["conv_service"]
    form_mgr = test_setup["form_mgr"]

    # Fill 2 fields
    await conv.process_user_input("My name is Vidhyadhar S.")
    await conv.process_user_input("My phone number is 9876543210.")
    await conv.process_user_input("Skip the address for now.")

    res = await conv.process_user_input("What information have I provided so far?")
    assert res["action"]["action"] == "GET_FORM_SUMMARY"
    assert "Vidhyadhar S" in res["response_text"]
    assert "9876543210" in res["response_text"]
    assert "Street Address" in res["response_text"]  # Skipped address

# 8 & 9. Gemini result becoming stale after newer user instruction & Stale Gemini cannot update form
@pytest.mark.asyncio
async def test_stale_gemini_result_cannot_update_form(test_setup):
    conv = test_setup["conv_service"]
    form_mgr = test_setup["form_mgr"]
    version_mgr = test_setup["version_mgr"]
    mock_ai = test_setup["mock_ai_provider"]

    # Set artificial delay on AI provider to simulate slow LLM response
    mock_ai.artificial_delay = 0.3

    # Start slow Input A (v11)
    task_a = asyncio.create_task(conv.process_user_input("My name is Vidhyadhar A"))

    # Rapid interruption by Input B (v12) before Input A finishes
    await asyncio.sleep(0.05)
    res_b = await conv.process_user_input("Actually, my name is Vidhyadhar B")

    res_a = await task_a

    # Input A must be marked as stale and rejected
    assert res_a["is_stale"] is True

    # Authoritative form state must strictly contain the newer Input B value
    state = form_mgr.get_state()
    assert state.fields["full_name"].value == "Vidhyadhar B"

# 10. Gemini-triggered postal validation with later user correction
@pytest.mark.asyncio
async def test_gemini_triggered_postal_validation_with_correction(test_setup):
    conv = test_setup["conv_service"]
    form_mgr = test_setup["form_mgr"]
    val_service = test_setup["val_service"]
    timeline = test_setup["timeline"]

    # 1. User provides postal code (triggers background validation)
    res_1 = await conv.process_user_input("Change my postal code to 600001")
    v1 = res_1["interaction_version"]
    assert res_1["action"]["action"] == "UPDATE_FIELD" or res_1["action"]["action"] == "CORRECT_FIELD"
    assert res_1["action"]["target_field"] == "postal_code"

    # Immediately, user interrupts and changes postal code to 600028
    res_2 = await conv.process_user_input("Actually, change postal code to 600028")
    v2 = res_2["interaction_version"]
    assert v2 > v1

    # Allow background validation tasks to complete
    await asyncio.sleep(0.5)

    # State must strictly have the newest postal code (600028)
    state = form_mgr.get_state()
    assert state.fields["postal_code"].value == "600028"

    # Check that older validation result was blocked by fence
    stale_blocked_events = [e for e in timeline if e.get("event_type") == "STALE_RESULT_BLOCKED"]
    assert len(stale_blocked_events) >= 1
    assert stale_blocked_events[0]["interaction_version"] == v1

# 11. Multiple rapid natural-language corrections
@pytest.mark.asyncio
async def test_multiple_rapid_corrections(test_setup):
    conv = test_setup["conv_service"]
    form_mgr = test_setup["form_mgr"]
    mock_ai = test_setup["mock_ai_provider"]
    mock_ai.artificial_delay = 0.1

    # Fire 3 rapid inputs in parallel
    t1 = asyncio.create_task(conv.process_user_input("My occupation is Designer"))
    await asyncio.sleep(0.02)
    t2 = asyncio.create_task(conv.process_user_input("Change my occupation to Data Analyst"))
    await asyncio.sleep(0.02)
    t3 = asyncio.create_task(conv.process_user_input("Actually, change my occupation to Software Developer"))

    r1, r2, r3 = await asyncio.gather(t1, t2, t3)

    # Only the newest should succeed, older ones are stale
    assert r3["success"] is True
    assert form_mgr.get_state().fields["occupation"].value == "Software Developer"
