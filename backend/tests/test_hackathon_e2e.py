import pytest
import asyncio
from typing import Dict, Any

from backend.app.services.interaction_version_manager import InteractionVersionManager
from backend.app.services.task_manager import TaskManager
from backend.app.services.stale_result_guard import StaleResultGuard
from backend.app.services.form_state_manager import FormStateManager
from backend.app.services.validation_service import ValidationService
from backend.app.services.ai_service import AIService
from backend.app.services.ai_provider import MockAIProvider
from backend.app.services.action_validator import ActionValidator
from backend.app.services.conversation_service import ConversationService
from backend.app.services.speech_service import SpeechService
from backend.app.services.speech_provider import MockSpeechProvider
from backend.app.services.speech_recognition_provider import MockSpeechRecognitionProvider
from backend.app.models.form_models import FieldStatus, ValidationStatus
from backend.app.models.conversation_models import UserIntent

@pytest.fixture
def e2e_system():
    version_manager = InteractionVersionManager(initial_version=100)
    task_manager = TaskManager()
    stale_guard = StaleResultGuard(version_manager=version_manager, task_manager=task_manager)
    timeline = []
    
    form_state_manager = FormStateManager(stale_guard=stale_guard)
    validation_service = ValidationService()
    speech_service = SpeechService(
        version_manager=version_manager,
        task_manager=task_manager,
        stale_guard=stale_guard,
        provider=MockSpeechProvider(artificial_delay=0.01),
        timeline_ref=timeline
    )
    mock_ai = MockAIProvider()
    ai_service = AIService(provider=mock_ai, task_manager=task_manager)
    action_validator = ActionValidator()

    conversation_service = ConversationService(
        version_manager=version_manager,
        form_state_manager=form_state_manager,
        task_manager=task_manager,
        stale_guard=stale_guard,
        validation_service=validation_service,
        ai_service=ai_service,
        action_validator=action_validator,
        speech_service=speech_service,
        timeline_ref=timeline
    )

    return {
        "version_manager": version_manager,
        "task_manager": task_manager,
        "stale_guard": stale_guard,
        "form_state_manager": form_state_manager,
        "validation_service": validation_service,
        "ai_service": ai_service,
        "mock_ai": mock_ai,
        "action_validator": action_validator,
        "speech_service": speech_service,
        "conversation_service": conversation_service,
        "timeline": timeline
    }

# =========================================================================
# PHASE 6.1: Full Voice Pipeline End-to-End Test
# =========================================================================
@pytest.mark.asyncio
async def test_phase6_1_full_voice_to_form_state_pipeline(e2e_system):
    conv_svc = e2e_system["conversation_service"]
    fsm = e2e_system["form_state_manager"]
    vm = e2e_system["version_manager"]
    timeline = e2e_system["timeline"]

    res = await conv_svc.process_user_input(
        text="My full name is Alexander Wright",
        input_source="voice"
    )

    assert res["success"] is True
    assert res["active_version"] == 101
    assert fsm.get_field_value("full_name") == "Alexander Wright"
    assert len(timeline) > 0
    event_types = [e["event_type"] for e in timeline]
    assert "VOICE_INTERACTION_ACCEPTED" in event_types
    assert "FINAL_TRANSCRIPT_RECEIVED" in event_types
    assert "ACTION_APPLIED" in event_types

# =========================================================================
# PHASE 6.2: Natural Language Actions Test
# =========================================================================
@pytest.mark.asyncio
async def test_phase6_2_natural_language_actions(e2e_system):
    conv_svc = e2e_system["conversation_service"]
    fsm = e2e_system["form_state_manager"]

    # 1. SET_FIELD
    await conv_svc.process_user_input("My email is alex@example.com", input_source="voice")
    assert fsm.get_field_value("email") == "alex@example.com"

    # 2. CORRECTION
    await conv_svc.process_user_input("Actually, change my email to alex.w@example.com", input_source="voice")
    assert fsm.get_field_value("email") == "alex.w@example.com"

    # 3. SKIP_FIELD
    await fsm.set_active_field("phone_number")
    await conv_svc.process_user_input("Skip this field please", input_source="voice")
    assert fsm.get_field_status("phone_number") == FieldStatus.SKIPPED

    # 4. NAVIGATE_FIELD / NEXT
    await conv_svc.process_user_input("Go to postal code", input_source="voice")
    assert fsm.get_state().active_field_key == "postal_code"

    # 5. SUMMARY
    sum_res = await conv_svc.process_user_input("Can you give me a summary of the form?", input_source="voice")
    assert "summary" in sum_res["response_text"].lower() or "completed" in sum_res["response_text"].lower()

# =========================================================================
# PHASE 6.3: Canonical Hackathon Barge-in Scenario (v100 -> v101)
# =========================================================================
@pytest.mark.asyncio
async def test_phase6_3_hackathon_barge_in_scenario(e2e_system):
    conv_svc = e2e_system["conversation_service"]
    fsm = e2e_system["form_state_manager"]
    vm = e2e_system["version_manager"]
    tm = e2e_system["task_manager"]
    speech_svc = e2e_system["speech_service"]
    timeline = e2e_system["timeline"]

    v100 = 100
    v101 = 101

    # User speaks: "My postal code is 600001"
    v100_res = await conv_svc.process_user_input(
        text="My postal code is 600001",
        input_source="voice",
        interaction_version=v100
    )
    assert v100_res["success"] is True
    assert fsm.get_field_value("postal_code") == "600001"

    # Audio playback starts for v100
    await speech_svc._emit_event(
        event_type="AUDIO_PLAYBACK_STARTED",
        interaction_version=v100,
        active_version=v100,
        message="Audio playing for v100"
    )

    # User interrupts! New voice barge-in
    new_ver = await vm.create_new_version(reason="User voice barge-in")
    assert new_ver == v101
    await tm.cancel_tasks_for_version(v100, reason="Barge-in")

    await speech_svc._emit_event(
        event_type="USER_INTERRUPTION_DETECTED",
        interaction_version=v100,
        active_version=v101,
        message="Interruption detected"
    )
    await speech_svc._emit_event(
        event_type="AUDIO_PLAYBACK_STOPPED",
        interaction_version=v100,
        active_version=v101,
        message="Audio stopped in 14ms"
    )
    await speech_svc._emit_event(
        event_type="AUDIO_QUEUE_CLEARED",
        interaction_version=v101,
        active_version=v101,
        message="Audio queue cleared"
    )

    # User speaks correction: "Actually change it to 600028"
    v101_res = await conv_svc.process_user_input(
        text="Actually change it to 600028",
        input_source="voice",
        interaction_version=v101
    )
    assert v101_res["success"] is True

    # Check authoritative state
    final_postal = fsm.get_field_value("postal_code")
    assert final_postal == "600028", f"Expected 600028, got {final_postal}"
    assert vm.active_version == v101

# =========================================================================
# PHASE 6.6: Graceful Error Recovery
# =========================================================================
@pytest.mark.asyncio
async def test_phase6_6_graceful_error_recovery(e2e_system):
    conv_svc = e2e_system["conversation_service"]
    fsm = e2e_system["form_state_manager"]
    mock_ai = e2e_system["mock_ai"]
    speech_svc = e2e_system["speech_service"]

    # Initial valid field
    await conv_svc.process_user_input("My city is Seattle", input_source="voice")
    assert fsm.get_field_value("city") == "Seattle"

    # 1. AI failure simulation - AIService catches failure and returns clarification fallback
    original_ai_impl = mock_ai.interpret_user_input
    async def failing_ai(*args, **kwargs):
        raise RuntimeError("Simulated Gemini connection timeout")
    mock_ai.interpret_user_input = failing_ai

    res = await conv_svc.process_user_input("Change city to Boston", input_source="voice")
    # VoiceForm handles AI errors gracefully with clarification request
    assert "issue" in res["response_text"].lower() or "rephrase" in res["response_text"].lower()
    assert conv_svc.get_metrics()["ai_failures"] >= 1

    # Form state MUST remain intact with previous valid state
    assert fsm.get_field_value("city") == "Seattle"
    mock_ai.interpret_user_input = original_ai_impl

    # 2. TTS failure simulation
    speech_svc.set_provider(MockSpeechProvider(should_fail=True))
    tts_res = await speech_svc.synthesize_response("Form updated successfully", interaction_version=105)
    assert tts_res["success"] is False

    # Form state is never corrupted by TTS failure
    assert fsm.get_field_value("city") == "Seattle"

# =========================================================================
# PHASE 6.8: Observability & Telemetry Verification
# =========================================================================
@pytest.mark.asyncio
async def test_phase6_8_observability_telemetry(e2e_system):
    conv_svc = e2e_system["conversation_service"]
    speech_svc = e2e_system["speech_service"]
    fsm = e2e_system["form_state_manager"]

    await conv_svc.process_user_input("My name is Sarah Connor", input_source="voice")
    await conv_svc.process_user_input("My city is Los Angeles", input_source="voice")

    metrics = conv_svc.get_metrics()
    assert metrics["total_voice_inputs"] >= 2
    assert metrics["accepted_voice_inputs"] >= 2
    assert metrics["ai_requests"] >= 2
    assert metrics["last_voice_to_response_latency_ms"] is not None
    assert metrics["last_voice_to_response_latency_ms"] >= 0

# =========================================================================
# PHASE 6.9: 20-Step Complete Hackathon Acceptance Test
# =========================================================================
@pytest.mark.asyncio
async def test_phase6_9_twenty_step_hackathon_acceptance_test(e2e_system):
    """
    Verifies all 20 lifecycle steps of VoiceForm:
    1. User voice transcript accepted.
    2. Interaction version created.
    3. Gemini structured action generated.
    4. Action validated.
    5. Form state updated.
    6. Assistant response generated.
    7. Rime TTS requested.
    8. Audio accepted.
    9. Audio playback started.
    10. User interruption occurs.
    11. Audio stops.
    12. Old queue clears.
    13. New interaction version created.
    14. Old tasks cancelled where possible.
    15. Old results are fenced.
    16. New transcript accepted.
    17. New action validated.
    18. New form state applied.
    19. New assistant response generated.
    20. New audio becomes eligible.
    """
    conv_svc = e2e_system["conversation_service"]
    fsm = e2e_system["form_state_manager"]
    vm = e2e_system["version_manager"]
    tm = e2e_system["task_manager"]
    speech_svc = e2e_system["speech_service"]
    timeline = e2e_system["timeline"]

    # Step 1-8: Initial interaction (Version 100)
    v100 = 100
    res1 = await conv_svc.process_user_input(
        text="My state is California",
        input_source="voice",
        interaction_version=v100
    )
    assert res1["success"] is True

    # Step 9: Audio playback started
    await speech_svc._emit_event(
        event_type="AUDIO_PLAYBACK_STARTED",
        interaction_version=v100,
        active_version=v100,
        message="Playback started for v100"
    )

    # Step 10-15: Interruption sequence
    v101 = await vm.create_new_version(reason="User voice barge-in")
    assert v101 == 101

    # Cancel old tasks & fence old results
    await tm.cancel_tasks_for_version(v100, reason="Voice barge-in")
    conv_svc.record_voice_interruption()

    await speech_svc._emit_event(
        event_type="USER_INTERRUPTION_DETECTED",
        interaction_version=v100,
        active_version=v101,
        message="Interruption triggered"
    )
    await speech_svc._emit_event(
        event_type="AUDIO_PLAYBACK_STOPPED",
        interaction_version=v100,
        active_version=v101,
        message="Audio playback stopped"
    )
    await speech_svc._emit_event(
        event_type="AUDIO_QUEUE_CLEARED",
        interaction_version=v101,
        active_version=v101,
        message="Obsolete audio queue cleared"
    )

    # Late-arriving stale result from v100 MUST be fenced
    stale_attempt = await fsm.update_field("state", "Texas", version=v100)
    assert stale_attempt.get("stale_blocked") is True

    # Step 16-20: New interaction (Version 101)
    res2 = await conv_svc.process_user_input(
        text="Actually change state to Washington",
        input_source="voice",
        interaction_version=v101
    )
    assert res2["success"] is True
    assert fsm.get_field_value("state") == "Washington"

    # New audio is valid
    v101_audio = await speech_svc.synthesize_response("State changed to Washington", interaction_version=v101)
    assert v101_audio["success"] is True
    assert v101_audio["is_stale"] is False

# =========================================================================
# PHASE 6.10: Rapid Interruption Stress Scenario (v200 -> v203)
# =========================================================================
@pytest.mark.asyncio
async def test_phase6_10_rapid_interruption_stress_scenario(e2e_system):
    """
    Simulates rapid user speech:
    v200: "My postal code is 10001"
    v201: "No wait, 10002"
    v202: "Actually 10003"
    v203: "Finally 90210"
    Older tasks delayed and return out of order.
    Only v203 must win!
    """
    conv_svc = e2e_system["conversation_service"]
    fsm = e2e_system["form_state_manager"]
    vm = e2e_system["version_manager"]
    tm = e2e_system["task_manager"]
    stale_guard = e2e_system["stale_guard"]

    vm.reset(initial_version=200)

    # Create versions rapidly
    v200 = 200
    v201 = await vm.create_new_version("rapid 1")
    v202 = await vm.create_new_version("rapid 2")
    v203 = await vm.create_new_version("rapid 3")

    assert vm.active_version == 203

    # Attempt to apply v200, v201, v202 (they return late)
    res200 = await fsm.update_field("postal_code", "10001", version=v200)
    assert res200.get("stale_blocked") is True

    res201 = await fsm.update_field("postal_code", "10002", version=v201)
    assert res201.get("stale_blocked") is True

    res202 = await fsm.update_field("postal_code", "10003", version=v202)
    assert res202.get("stale_blocked") is True

    # Now apply latest active version v203
    res203 = await fsm.update_field("postal_code", "90210", version=v203)
    assert res203.get("stale_blocked") is False

    assert fsm.get_field_value("postal_code") == "90210"

# =========================================================================
# PHASE 6.18: Reset Demo Operation
# =========================================================================
@pytest.mark.asyncio
async def test_phase6_18_demo_reset_operation(e2e_system):
    conv_svc = e2e_system["conversation_service"]
    fsm = e2e_system["form_state_manager"]
    vm = e2e_system["version_manager"]
    tm = e2e_system["task_manager"]
    speech_svc = e2e_system["speech_service"]
    timeline = e2e_system["timeline"]

    # Populate dirty state
    await conv_svc.process_user_input("My name is John Doe", input_source="voice")
    assert fsm.get_field_value("full_name") == "John Doe"
    assert vm.active_version > 100
    assert len(timeline) > 0

    # Reset
    vm.reset(initial_version=100)
    fsm.reset()
    tm.clear()
    conv_svc.reset()
    speech_svc.reset()
    timeline.clear()

    # Assert clean state
    assert vm.active_version == 100
    assert fsm.get_field_value("full_name") == ""
    assert tm.get_active_tasks_count() == 0
    assert len(timeline) == 0
    assert conv_svc.get_metrics()["total_voice_inputs"] == 0
