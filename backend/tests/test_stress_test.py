import pytest
import asyncio
from backend.app.services.interaction_version_manager import InteractionVersionManager
from backend.app.services.task_manager import TaskManager
from backend.app.services.stale_result_guard import StaleResultGuard
from backend.app.services.form_state_manager import FormStateManager
from backend.app.services.validation_service import ValidationService
from backend.app.services.stress_test_service import StressTestService
from backend.app.models.form_models import FieldStatus, ValidationStatus

def create_test_harness():
    vm = InteractionVersionManager(initial_version=10)
    tm = TaskManager()
    guard = StaleResultGuard(version_manager=vm, task_manager=tm)
    fsm = FormStateManager(stale_guard=guard)
    val_svc = ValidationService(default_delay=0.0)

    # Wire invalidation listener
    def on_invalidation(old_ver, new_ver):
        asyncio.create_task(tm.cancel_tasks_for_version(old_ver))
    vm.add_invalidation_listener(on_invalidation)

    stress_svc = StressTestService(
        version_manager=vm,
        task_manager=tm,
        stale_guard=guard,
        form_state_manager=fsm,
        validation_service=val_svc
    )
    return vm, tm, guard, fsm, val_svc, stress_svc

@pytest.mark.asyncio
async def test_full_cancellable_stress_test_flow():
    """Test 1: Cancellable Task Mode."""
    vm, tm, guard, fsm, val_svc, stress_svc = create_test_harness()

    result = await stress_svc.run_stress_test(
        mode="cancellable",
        old_postal_code="600001",
        new_postal_code="600028",
        validation_delay_seconds=0.4,
        interrupt_after_seconds=0.1
    )

    assert result["test_success"] is True
    assert result["mode"] == "cancellable"
    assert result["final_interaction_version"] == 12  # 10 -> 11 (req 1) -> 12 (req 2)
    assert result["final_form_state"]["fields"]["postal_code"]["value"] == "600028"
    assert result["final_form_state"]["fields"]["postal_code"]["status"] == FieldStatus.CONFIRMED.value

    # Check event sequence
    event_types = [e["event_type"] for e in result["event_timeline"]]
    assert "INTERACTION_STARTED" in event_types
    assert "VALIDATION_STARTED" in event_types
    assert "INTERRUPTION_DETECTED" in event_types
    assert "TASK_CANCELLED" in event_types
    assert "VALIDATION_RESULT_ACCEPTED" in event_types
    assert "FORM_STATE_UPDATED" in event_types

@pytest.mark.asyncio
async def test_full_uncancellable_stress_test_flow():
    """Test 2: Uncancellable Task Mode (proves version fencing guarantees correctness)."""
    vm, tm, guard, fsm, val_svc, stress_svc = create_test_harness()

    result = await stress_svc.run_stress_test(
        mode="uncancellable",
        old_postal_code="600001",
        new_postal_code="600028",
        validation_delay_seconds=0.4,
        interrupt_after_seconds=0.1
    )

    assert result["test_success"] is True
    assert result["mode"] == "uncancellable"
    assert result["stale_results_blocked"] >= 1
    assert result["final_form_state"]["fields"]["postal_code"]["value"] == "600028"
    assert result["final_form_state"]["fields"]["postal_code"]["status"] == FieldStatus.CONFIRMED.value

    # Event timeline must contain STALE_RESULT_BLOCKED
    event_types = [e["event_type"] for e in result["event_timeline"]]
    assert "INTERRUPTION_DETECTED" in event_types
    assert "VERSION_INVALIDATED" in event_types
    assert "STALE_RESULT_BLOCKED" in event_types
    assert "VALIDATION_RESULT_ACCEPTED" in event_types

@pytest.mark.asyncio
async def test_old_postal_code_cannot_overwrite_new_value():
    """Test 3: Old result return does not overwrite newer user input."""
    vm, tm, guard, fsm, val_svc, stress_svc = create_test_harness()

    result = await stress_svc.run_stress_test(
        mode="uncancellable",
        old_postal_code="600001",
        new_postal_code="600028",
        validation_delay_seconds=0.3,
        interrupt_after_seconds=0.1
    )

    final_postal = fsm.get_state().fields["postal_code"]
    assert final_postal.value != "600001"
    assert final_postal.value == "600028"
    assert final_postal.interaction_version == 12

@pytest.mark.asyncio
async def test_final_form_state_contains_newest_valid_postal_code():
    """Test 4: Final state is authoritative and confirmed with valid metadata."""
    vm, tm, guard, fsm, val_svc, stress_svc = create_test_harness()

    result = await stress_svc.run_stress_test(
        mode="uncancellable",
        old_postal_code="600001",
        new_postal_code="600028",
        validation_delay_seconds=0.3,
        interrupt_after_seconds=0.1
    )

    postal_field = result["final_form_state"]["fields"]["postal_code"]
    assert postal_field["value"] == "600028"
    assert postal_field["validation_status"] == ValidationStatus.VALID.value
    assert postal_field["status"] == FieldStatus.CONFIRMED.value
    assert postal_field["validation_details"]["city"] == "Chennai"

@pytest.mark.asyncio
async def test_event_timeline_contains_stale_result_blocked_in_uncancellable_mode():
    """Test 5: Explicit verification of STALE_RESULT_BLOCKED event with version details."""
    vm, tm, guard, fsm, val_svc, stress_svc = create_test_harness()

    result = await stress_svc.run_stress_test(
        mode="uncancellable",
        old_postal_code="600001",
        new_postal_code="600028",
        validation_delay_seconds=0.3,
        interrupt_after_seconds=0.1
    )

    stale_events = [e for e in result["event_timeline"] if e["event_type"] == "STALE_RESULT_BLOCKED"]
    assert len(stale_events) >= 1
    stale_evt = stale_events[0]
    assert stale_evt["is_stale_blocked"] is True
    assert stale_evt["interaction_version"] == 11
    assert stale_evt["active_version"] == 12

@pytest.mark.asyncio
async def test_metrics_correctly_count_stale_results():
    """Test 6: System metrics tracker accurately reflects blocked stale results."""
    vm, tm, guard, fsm, val_svc, stress_svc = create_test_harness()

    assert guard.stale_blocks_count == 0

    await stress_svc.run_stress_test(
        mode="uncancellable",
        old_postal_code="600001",
        new_postal_code="600028",
        validation_delay_seconds=0.3,
        interrupt_after_seconds=0.1
    )

    assert guard.stale_blocks_count == 1
    assert len(guard.get_blocked_events()) == 1

@pytest.mark.asyncio
async def test_multiple_consecutive_runs_do_not_leak_state():
    """Test 7: Multiple consecutive stress-test runs isolate state cleanly."""
    vm, tm, guard, fsm, val_svc, stress_svc = create_test_harness()

    # Run 1
    res1 = await stress_svc.run_stress_test(
        mode="uncancellable",
        old_postal_code="600001",
        new_postal_code="600028",
        validation_delay_seconds=0.2,
        interrupt_after_seconds=0.05,
        reset_before_run=True
    )
    assert res1["test_success"] is True
    assert res1["stale_results_blocked"] == 1
    assert res1["final_interaction_version"] == 12

    # Run 2 with different postal codes
    res2 = await stress_svc.run_stress_test(
        mode="uncancellable",
        old_postal_code="10001",
        new_postal_code="94103",
        validation_delay_seconds=0.2,
        interrupt_after_seconds=0.05,
        reset_before_run=True
    )
    assert res2["test_success"] is True
    assert res2["stale_results_blocked"] == 1
    assert res2["final_form_state"]["fields"]["postal_code"]["value"] == "94103"
    assert res2["final_interaction_version"] == 12
    # Ensure no event leak from run 1
    old_inputs = [e for e in res2["event_timeline"] if "600001" in e.get("message", "")]
    assert len(old_inputs) == 0
