import pytest
import asyncio
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
from backend.app.services.speech_provider import MockSpeechProvider, generate_minimal_valid_wav_base64
from backend.app.models.conversation_models import UserIntent
from backend.app.models.form_models import FieldStatus

@pytest.fixture
def speech_pipeline():
    """Sets up a clean, isolated version-fenced speech pipeline with MockSpeechProvider."""
    version_mgr = InteractionVersionManager(initial_version=20)
    task_mgr = TaskManager()
    stale_guard = StaleResultGuard(version_manager=version_mgr, task_manager=task_mgr)
    form_mgr = FormStateManager(stale_guard=stale_guard)
    val_service = ValidationService()
    timeline = []
    
    mock_speech_provider = MockSpeechProvider(artificial_delay=0.0)
    speech_svc = SpeechService(
        version_manager=version_mgr,
        task_manager=task_mgr,
        stale_guard=stale_guard,
        provider=mock_speech_provider,
        timeline_ref=timeline
    )

    mock_ai = MockAIProvider()
    ai_svc = AIService(provider=mock_ai, task_manager=task_mgr)
    validator = ActionValidator()

    conversation_svc = ConversationService(
        version_manager=version_mgr,
        form_state_manager=form_mgr,
        task_manager=task_mgr,
        stale_guard=stale_guard,
        validation_service=val_service,
        ai_service=ai_svc,
        action_validator=validator,
        speech_service=speech_svc,
        timeline_ref=timeline
    )

    # Wire invalidation listener
    def on_inval(old_v: int, new_v: int):
        asyncio.create_task(task_mgr.cancel_tasks_for_version(old_v))
    version_mgr.add_invalidation_listener(on_inval)

    return {
        "version_mgr": version_mgr,
        "task_mgr": task_mgr,
        "stale_guard": stale_guard,
        "form_mgr": form_mgr,
        "speech_svc": speech_svc,
        "speech_provider": mock_speech_provider,
        "conversation_svc": conversation_svc,
        "ai_provider": mock_ai,
        "timeline": timeline
    }


@pytest.mark.asyncio
async def test_fresh_speech_result_accepted(speech_pipeline):
    """Test 1: Fresh speech generation result for active interaction version is accepted."""
    svc: SpeechService = speech_pipeline["speech_svc"]
    version_mgr: InteractionVersionManager = speech_pipeline["version_mgr"]

    active_ver = version_mgr.active_version # 20
    res = await svc.synthesize_response(
        text="Hello, your name has been updated to John Doe.",
        interaction_version=active_ver
    )

    assert res["success"] is True
    assert res["is_stale"] is False
    assert res["interaction_version"] == 20
    assert res["active_version"] == 20
    assert res["audio_result"]["audio_base64"] is not None
    assert svc.completed_tts_requests == 1
    assert svc.stale_tts_results_blocked == 0


@pytest.mark.asyncio
async def test_stale_speech_generation_result_blocked(speech_pipeline):
    """Test 2: Speech generation result returning after active version advanced is blocked as stale."""
    svc: SpeechService = speech_pipeline["speech_svc"]
    version_mgr: InteractionVersionManager = speech_pipeline["version_mgr"]
    provider: MockSpeechProvider = speech_pipeline["speech_provider"]

    # Add delay to speech generation
    provider.artificial_delay = 0.2

    # Launch TTS for v20 in background (uncancellable to ensure it finishes returning)
    tts_task = asyncio.create_task(
        svc.synthesize_response(
            text="Your postal code is being processed.",
            interaction_version=20,
            uncancellable=True
        )
    )

    # Before TTS completes, user interrupts creating v21
    await asyncio.sleep(0.05)
    await version_mgr.create_new_version(reason="User voice interruption: 'Actually no'")
    assert version_mgr.active_version == 21

    # Await delayed v20 TTS completion
    res = await tts_task

    assert res["success"] is False
    assert res["is_stale"] is True
    assert res["interaction_version"] == 20
    assert res["active_version"] == 21
    assert "blocked" in res["error"].lower()
    assert svc.stale_tts_results_blocked == 1


@pytest.mark.asyncio
async def test_new_interaction_cancels_old_tts_task(speech_pipeline):
    """Test 3: New interaction cancels cancellable in-flight TTS task."""
    svc: SpeechService = speech_pipeline["speech_svc"]
    version_mgr: InteractionVersionManager = speech_pipeline["version_mgr"]
    provider: MockSpeechProvider = speech_pipeline["speech_provider"]

    provider.artificial_delay = 0.5

    # Launch cancellable TTS for v20
    tts_task = asyncio.create_task(
        svc.synthesize_response(
            text="Updating your address details.",
            interaction_version=20,
            uncancellable=False
        )
    )

    await asyncio.sleep(0.05)
    # Trigger interruption
    await version_mgr.create_new_version(reason="User interruption")
    await asyncio.sleep(0.05)

    res = await tts_task
    assert res["is_stale"] is True
    assert svc.cancelled_tts_requests >= 1 or svc.stale_tts_results_blocked >= 1


@pytest.mark.asyncio
async def test_uncancellable_old_tts_task_cannot_enqueue_audio(speech_pipeline):
    """Test 4: Uncancellable old TTS task that completes cannot deliver audio to playback."""
    svc: SpeechService = speech_pipeline["speech_svc"]
    version_mgr: InteractionVersionManager = speech_pipeline["version_mgr"]
    provider: MockSpeechProvider = speech_pipeline["speech_provider"]

    provider.artificial_delay = 0.15

    task = asyncio.create_task(
        svc.synthesize_response(
            text="Uncancellable slow network audio stream.",
            interaction_version=20,
            uncancellable=True
        )
    )

    await asyncio.sleep(0.05)
    await version_mgr.create_new_version(reason="User correction v21")
    await version_mgr.create_new_version(reason="User correction v22")

    res = await task
    assert res["success"] is False
    assert res["is_stale"] is True
    assert res["active_version"] == 22
    assert svc.stale_tts_results_blocked >= 1


@pytest.mark.asyncio
async def test_audio_payload_rejected_at_checkpoint_1_if_already_stale(speech_pipeline):
    """Test 5: Speech generation requested for already stale version is rejected immediately at Checkpoint 1."""
    svc: SpeechService = speech_pipeline["speech_svc"]
    version_mgr: InteractionVersionManager = speech_pipeline["version_mgr"]

    # Active version is 20, but request is for obsolete version 15
    res = await svc.synthesize_response(
        text="Obsolete request",
        interaction_version=15
    )

    assert res["success"] is False
    assert res["is_stale"] is True
    assert res["interaction_version"] == 15
    assert res["active_version"] == 20
    assert "obsolete before start" in res["error"].lower()


@pytest.mark.asyncio
async def test_multiple_rapid_versions_leaves_only_latest_audio_valid(speech_pipeline):
    """Test 6: Multiple rapid interactions (v30, v31, v32) leave only the latest audio valid."""
    svc: SpeechService = speech_pipeline["speech_svc"]
    version_mgr: InteractionVersionManager = speech_pipeline["version_mgr"]
    provider: MockSpeechProvider = speech_pipeline["speech_provider"]
    provider.artificial_delay = 0.08

    version_mgr.reset(initial_version=30)

    t1 = asyncio.create_task(svc.synthesize_response("Audio 30", interaction_version=30, uncancellable=True))
    await asyncio.sleep(0.02)
    await version_mgr.create_new_version(reason="Input 31")
    t2 = asyncio.create_task(svc.synthesize_response("Audio 31", interaction_version=31, uncancellable=True))
    await asyncio.sleep(0.02)
    await version_mgr.create_new_version(reason="Input 32")
    t3 = asyncio.create_task(svc.synthesize_response("Audio 32", interaction_version=32, uncancellable=True))

    r1, r2, r3 = await asyncio.gather(t1, t2, t3)

    assert r1["is_stale"] is True
    assert r2["is_stale"] is True
    assert r3["is_stale"] is False
    assert r3["success"] is True
    assert r3["interaction_version"] == 32
    assert r3["active_version"] == 32


@pytest.mark.asyncio
async def test_tts_failure_does_not_corrupt_form_state(speech_pipeline):
    """Test 7: TTS generation failure does not break conversation or corrupt form state."""
    svc: SpeechService = speech_pipeline["speech_svc"]
    provider: MockSpeechProvider = speech_pipeline["speech_provider"]
    form_mgr: FormStateManager = speech_pipeline["form_mgr"]
    version_mgr: InteractionVersionManager = speech_pipeline["version_mgr"]

    # Update a field first
    await form_mgr.update_field("full_name", "Alice Walker", version_mgr.active_version)
    assert form_mgr.get_state().fields["full_name"].value == "Alice Walker"

    # Configure provider to fail
    provider.should_fail = True
    provider.failure_message = "Simulated Rime API HTTP 503 Service Unavailable"

    res = await svc.synthesize_response(
        text="Alice Walker has been confirmed.",
        interaction_version=version_mgr.active_version
    )

    assert res["success"] is False
    assert "503" in res["error"]
    # Form state remains intact and uncorrupted
    assert form_mgr.get_state().fields["full_name"].value == "Alice Walker"
    assert form_mgr.get_state().fields["full_name"].status == FieldStatus.CONFIRMED


@pytest.mark.asyncio
async def test_speech_lifecycle_events_contain_correct_versions(speech_pipeline):
    """Test 8: Speech lifecycle events in timeline contain exact interaction and active versions."""
    svc: SpeechService = speech_pipeline["speech_svc"]
    version_mgr: InteractionVersionManager = speech_pipeline["version_mgr"]
    timeline = speech_pipeline["timeline"]

    res = await svc.synthesize_response(
        text="Postal code updated to 600028.",
        interaction_version=20
    )
    assert res["success"] is True

    # Record playback event
    await svc.record_audio_playback_event(
        event_type="AUDIO_PLAYBACK_STARTED",
        interaction_version=20,
        task_id=res["task_id"]
    )

    event_types = [e["event_type"] for e in timeline]
    assert "TTS_REQUEST_STARTED" in event_types
    assert "TTS_GENERATION_STARTED" in event_types
    assert "TTS_GENERATION_COMPLETED" in event_types
    assert "TTS_RESULT_RETURNED" in event_types
    assert "AUDIO_PLAYBACK_STARTED" in event_types

    for e in timeline:
        if e["event_type"].startswith("TTS_") or e["event_type"].startswith("AUDIO_"):
            assert e["interaction_version"] == 20
            assert e["active_version"] == 20
            assert "id" in e
            assert "timestamp" in e


@pytest.mark.asyncio
async def test_conversation_service_triggers_speech_synthesis(speech_pipeline):
    """Test 9: End-to-end ConversationService produces assistant response and executes versioned TTS synthesis."""
    conv_svc: ConversationService = speech_pipeline["conversation_svc"]
    ai: MockAIProvider = speech_pipeline["ai_provider"]
    svc: SpeechService = speech_pipeline["speech_svc"]

    ai.set_forced_response(
        text_key="My phone number is 9876543210",
        response_dict={
            "action": UserIntent.UPDATE_FIELD.value,
            "target_field": "phone_number",
            "value": "9876543210",
            "requires_validation": False,
            "response_text": "I've recorded your phone number as 9876543210."
        }
    )

    res = await conv_svc.process_user_input("My phone number is 9876543210")
    assert res["success"] is True
    assert res["response_text"] == "I've recorded your phone number as 9876543210."

    # Allow async TTS dispatch task to run
    await asyncio.sleep(0.1)
    assert svc.completed_tts_requests >= 1
