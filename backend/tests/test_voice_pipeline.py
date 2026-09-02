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

@pytest.fixture
def voice_services():
    version_manager = InteractionVersionManager(initial_version=10)
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

    def on_inval(old_v: int, new_v: int):
        asyncio.create_task(task_manager.cancel_tasks_for_version(old_v))
    version_manager.add_invalidation_listener(on_inval)
    
    return {
        "version_manager": version_manager,
        "task_manager": task_manager,
        "stale_guard": stale_guard,
        "form_state_manager": form_state_manager,
        "validation_service": validation_service,
        "speech_service": speech_service,
        "conversation_service": conversation_service,
        "timeline": timeline
    }

@pytest.mark.asyncio
async def test_req1_voice_transcript_enters_same_pipeline_as_text(voice_services):
    """Req 1: Voice transcript enters the exact same conversation pipeline as text."""
    conv = voice_services["conversation_service"]
    fsm = voice_services["form_state_manager"]

    result = await conv.process_user_input("My name is John Doe", input_source="voice")

    assert result["success"] is True
    assert result["is_stale"] is False
    assert result["active_version"] == 11
    form = fsm.get_state()
    assert form.fields["full_name"].value == "John Doe"
    assert form.fields["full_name"].interaction_version == 11

@pytest.mark.asyncio
async def test_req2_voice_input_creates_interaction_version(voice_services):
    """Req 2: Voice input strictly increments and tags interaction version."""
    vm = voice_services["version_manager"]
    conv = voice_services["conversation_service"]

    assert vm.active_version == 10
    res1 = await conv.process_user_input("My email is test@example.com", input_source="voice")
    assert res1["interaction_version"] == 11
    assert vm.active_version == 11

    res2 = await conv.process_user_input("My phone number is 555-123-4567", input_source="voice")
    assert res2["interaction_version"] == 12
    assert vm.active_version == 12

@pytest.mark.asyncio
async def test_req3_voice_interruption_advances_version_and_invalidates_prior_audio(voice_services):
    """Req 3: Starting voice input interrupts currently playing audio and supersedes version."""
    vm = voice_services["version_manager"]
    speech = voice_services["speech_service"]
    conv = voice_services["conversation_service"]

    # TTS task for v10
    tts_v10 = asyncio.create_task(
        speech.synthesize_response("Speaking v10 response", interaction_version=10, uncancellable=True)
    )

    # Voice interruption occurs
    v11 = await vm.create_new_version(reason="User voice barge-in")
    await conv._emit_event(
        event_type="AUDIO_INTERRUPTED_FOR_USER_INPUT",
        interaction_version=10,
        active_version=v11,
        message="Audio v10 interrupted by user speech"
    )

    v10_res = await tts_v10
    assert v10_res["is_stale"] is True
    assert v10_res["active_version"] == 11

@pytest.mark.asyncio
async def test_req4_voice_interruption_clears_obsolete_queue(voice_services):
    """Req 4: Speech service and version manager block obsolete queued items."""
    speech = voice_services["speech_service"]
    vm = voice_services["version_manager"]

    # Start slow task for v10
    speech.set_provider(MockSpeechProvider(artificial_delay=0.1))
    t1 = asyncio.create_task(speech.synthesize_response("Queue Item 1", interaction_version=10, uncancellable=True))
    
    # Interruption
    await vm.create_new_version(reason="Voice interruption")
    res1 = await t1

    assert res1["is_stale"] is True
    assert res1["success"] is False

@pytest.mark.asyncio
async def test_req5_old_tasks_cancelled_on_voice_interruption(voice_services):
    """Req 5: Old cancellable interaction tasks are cancelled on voice interruption."""
    tm = voice_services["task_manager"]
    vm = voice_services["version_manager"]

    # Register active task for v10
    task_rec = await tm.register_task(name="AI_PROCESS_V10", version=10, target_field="postal_code")
    assert task_rec.status.value == "ACTIVE"

    # Voice interruption creates v11
    await vm.create_new_version(reason="Voice barge-in")
    await asyncio.sleep(0.01)

    cancelled_task = tm.get_task(task_rec.task_id)
    assert cancelled_task.status.value == "CANCELLED"

@pytest.mark.asyncio
async def test_req6_old_ai_results_blocked_after_voice_interruption(voice_services):
    """Req 6: Stale AI results returning after a voice interruption are discarded."""
    vm = voice_services["version_manager"]
    fsm = voice_services["form_state_manager"]

    # Simulate AI processing for v10 superseded before mutation
    await vm.create_new_version(reason="Voice interruption for v11")
    
    # Attempting to mutate v10 into form state
    res = await fsm.update_field("city", "OldCity", version=10)
    assert res.get("stale_blocked") is True
    assert fsm.get_state().fields["city"].value == ""

@pytest.mark.asyncio
async def test_req7_old_validation_results_cannot_overwrite_newer_voice_input(voice_services):
    """Req 7: Stale postal code validation from old version cannot overwrite newer voice input."""
    val = voice_services["validation_service"]
    vm = voice_services["version_manager"]
    fsm = voice_services["form_state_manager"]

    # User set v10 postal code 600001
    await fsm.update_field("postal_code", "600001", version=10)
    val_task_v10 = asyncio.create_task(val.validate_postal_code("600001", custom_delay=0.1))

    # User voice barge-in for v11 sets 600028
    await vm.create_new_version(reason="Voice correction")
    await fsm.update_field("postal_code", "600028", version=11)

    v10_val_res = await val_task_v10
    # Attempting to apply stale validation to form state
    apply_res = await fsm.update_field(
        "postal_code",
        v10_val_res["postal_code"],
        version=10,
        status=FieldStatus.CONFIRMED,
        validation_status=ValidationStatus.VALID
    )
    assert apply_res.get("stale_blocked") is True
    assert fsm.get_state().fields["postal_code"].value == "600028"

@pytest.mark.asyncio
async def test_req8_old_tts_results_cannot_play_after_newer_voice_interaction(voice_services):
    """Req 8: Old TTS response cannot become active audio after voice interruption."""
    speech = voice_services["speech_service"]
    vm = voice_services["version_manager"]
    speech.set_provider(MockSpeechProvider(artificial_delay=0.1))

    t_v10 = asyncio.create_task(speech.synthesize_response("Old TTS v10", interaction_version=10, uncancellable=True))
    await asyncio.sleep(0.02)

    # Newer voice interaction v11
    await vm.create_new_version(reason="New voice input")
    res_v10 = await t_v10

    assert res_v10["is_stale"] is True
    assert res_v10["active_version"] == 11

@pytest.mark.asyncio
async def test_req9_final_voice_transcript_updates_correct_field(voice_services):
    """Req 9: Voice transcript accurately targets and updates intended form field."""
    conv = voice_services["conversation_service"]
    fsm = voice_services["form_state_manager"]

    await conv.process_user_input("My city is Seattle", input_source="voice")
    assert fsm.get_state().fields["city"].value == "Seattle"

@pytest.mark.asyncio
async def test_req10_multiple_rapid_voice_interactions_newest_wins(voice_services):
    """Req 10: Multiple rapid voice inputs leave only the newest version authoritative."""
    conv = voice_services["conversation_service"]
    fsm = voice_services["form_state_manager"]

    await conv.process_user_input("My address is 100 Main St", input_source="voice")
    await conv.process_user_input("Actually change my address to 200 Broadway", input_source="voice")
    await conv.process_user_input("No change my address to 300 Market Street", input_source="voice")

    assert fsm.get_state().fields["address"].value == "300 Market Street"
    assert fsm.get_state().fields["address"].interaction_version == 13

@pytest.mark.asyncio
async def test_req11_permission_denied_does_not_corrupt_form_state(voice_services):
    """Req 11: Microphone permission denied does not corrupt form state or versioning."""
    fsm = voice_services["form_state_manager"]
    vm = voice_services["version_manager"]

    provider = MockSpeechRecognitionProvider(permission_denied=True)
    rec_res = await provider.recognize()

    assert rec_res["success"] is False
    assert rec_res["is_permission_denied"] is True
    assert fsm.get_state().fields["full_name"].value == ""
    assert vm.active_version == 10

@pytest.mark.asyncio
async def test_req12_speech_recognition_failure_does_not_corrupt_form_state(voice_services):
    """Req 12: Speech recognition engine failure leaves state pristine."""
    fsm = voice_services["form_state_manager"]
    vm = voice_services["version_manager"]

    provider = MockSpeechRecognitionProvider(should_fail=True, error_message="Network audio stream drop")
    rec_res = await provider.recognize()

    assert rec_res["success"] is False
    assert rec_res["error"] == "Network audio stream drop"
    assert fsm.get_state().fields["full_name"].value == ""
    assert vm.active_version == 10

@pytest.mark.asyncio
async def test_req13_mock_recognition_interim_to_final_flow(voice_services):
    """Req 13: Mock speech recognition steps through interim transcripts to final result."""
    interim_received = []
    provider = MockSpeechRecognitionProvider(
        final_transcript="My postal code is 600028",
        interim_steps=["My postal", "My postal code", "My postal code is 600028"],
        artificial_delay=0.01
    )

    def on_interim(text: str):
        interim_received.append(text)

    rec_res = await provider.recognize(interim_callback=on_interim)
    assert rec_res["success"] is True
    assert rec_res["transcript"] == "My postal code is 600028"
    assert len(interim_received) == 3
    assert interim_received[-1] == "My postal code is 600028"

@pytest.mark.asyncio
async def test_req14_deterministic_voice_barge_in_v80_to_v81_scenario(voice_services):
    """
    Req 14: Deterministic End-to-End Voice Barge-in Scenario:
    v80 Voice Input: 'My postal code is 600001'
    v80 TTS Audio starts playing.
    User interrupts with v81 Voice Input: 'Actually change it to 600028'.
    v80 TTS Audio is stopped and blocked as stale.
    v81 Action is applied, validation starts, and fresh v81 audio is generated.
    Final postal_code must equal 600028.
    """
    vm = voice_services["version_manager"]
    fsm = voice_services["form_state_manager"]
    conv = voice_services["conversation_service"]
    speech = voice_services["speech_service"]

    # 1. Reset to v79 so first voice input creates v80
    vm.reset(initial_version=79)
    speech.set_provider(MockSpeechProvider(artificial_delay=0.3))

    # 2. Voice input v80 arrives
    v80_res = await conv.process_user_input("My postal code is 600001", input_source="voice")
    assert v80_res["interaction_version"] == 80
    assert vm.active_version == 80

    # 3. Simulate slow v80 speech synthesis task
    v80_tts_task = asyncio.create_task(
        speech.synthesize_response(
            text="Setting postal code to 600001.",
            interaction_version=80,
            uncancellable=True
        )
    )

    # 4. Voice barge-in occurs while v80 audio is generating/playing
    await asyncio.sleep(0.05)
    v81_version = await vm.create_new_version(reason="User voice barge-in: 'Actually change it to 600028'")
    assert v81_version == 81

    # 5. User speaks Version 81 transcript
    v81_res = await conv.process_user_input(
        "Actually change it to 600028",
        input_source="voice",
        interaction_version=v81_version
    )
    assert v81_res["interaction_version"] == 81
    assert v81_res["success"] is True

    # 6. Await slow v80 TTS - it must be blocked as stale
    v80_tts_res = await v80_tts_task
    assert v80_tts_res["is_stale"] is True
    assert v80_tts_res["success"] is False

    # 7. Generate fresh v81 audio
    v81_tts_res = await speech.synthesize_response(
        text="Updated postal code to 600028.",
        interaction_version=81
    )
    assert v81_tts_res["success"] is True
    assert v81_tts_res["is_stale"] is False

    # 8. Check final authoritative form state
    final_state = fsm.get_state()
    assert final_state.fields["postal_code"].value == "600028"
    assert final_state.fields["postal_code"].interaction_version == 81
