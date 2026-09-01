import pytest
from backend.app.services.interaction_version_manager import InteractionVersionManager
from backend.app.services.task_manager import TaskManager
from backend.app.services.stale_result_guard import StaleResultGuard
from backend.app.services.form_state_manager import FormStateManager
from backend.app.models.form_models import FieldStatus, ValidationStatus

@pytest.mark.asyncio
async def test_normal_field_update():
    vm = InteractionVersionManager(initial_version=10)
    tm = TaskManager()
    guard = StaleResultGuard(version_manager=vm, task_manager=tm)
    fsm = FormStateManager(stale_guard=guard)

    res = await fsm.update_field("full_name", "Vidhyadhar S", version=10, status=FieldStatus.CONFIRMED)
    assert res["success"] is True
    assert res["stale_blocked"] is False

    state = fsm.get_state()
    assert state.fields["full_name"].value == "Vidhyadhar S"
    assert state.fields["full_name"].status == FieldStatus.CONFIRMED
    assert state.fields["full_name"].interaction_version == 10

@pytest.mark.asyncio
async def test_user_correction_replaces_previous_value():
    vm = InteractionVersionManager(initial_version=10)
    tm = TaskManager()
    guard = StaleResultGuard(version_manager=vm, task_manager=tm)
    fsm = FormStateManager(stale_guard=guard)

    # Initial input: Occupation = "Data Analyst" (v10)
    await fsm.update_field("occupation", "Data Analyst", version=10)
    assert fsm.get_state().fields["occupation"].value == "Data Analyst"

    # User correction: Occupation = "Software Developer" (v11)
    v11 = await vm.create_new_version(reason="User correction")
    await fsm.update_field("occupation", "Software Developer", version=v11)

    state = fsm.get_state()
    assert state.fields["occupation"].value == "Software Developer"
    assert state.fields["occupation"].interaction_version == 11

@pytest.mark.asyncio
async def test_stale_validation_result_cannot_overwrite_newer_value():
    vm = InteractionVersionManager(initial_version=10)
    tm = TaskManager()
    guard = StaleResultGuard(version_manager=vm, task_manager=tm)
    fsm = FormStateManager(stale_guard=guard)

    # Step 1: User enters Postal Code 600001 (v10)
    await fsm.update_field("postal_code", "600001", version=10, status=FieldStatus.VALIDATING)
    task_v10 = await tm.register_task("postal_validation", version=10, target_field="postal_code")

    # Step 2: User interrupts before validation completes, changes to 600028 (v11)
    v11 = await vm.create_new_version(reason="User changed postal code")
    await fsm.update_field("postal_code", "600028", version=v11, status=FieldStatus.CONFIRMED)
    task_v11 = await tm.register_task("postal_validation", version=11, target_field="postal_code")

    # Step 3: Delayed validation for v10 (600001) finishes and tries to apply
    res_v10 = await fsm.apply_validation_result(
        field_name="postal_code",
        version=10,
        is_valid=True,
        validation_details={"city": "Old City", "state": "Old State"},
        task_id=task_v10.task_id
    )

    assert res_v10["success"] is False
    assert res_v10["stale_blocked"] is True

    # State must NOT have been overwritten by v10 result
    state = fsm.get_state()
    assert state.fields["postal_code"].value == "600028"
    assert state.fields["postal_code"].interaction_version == 11

    # Step 4: Validation for v11 finishes and applies
    res_v11 = await fsm.apply_validation_result(
        field_name="postal_code",
        version=11,
        is_valid=True,
        validation_details={"city": "Chennai", "state": "Tamil Nadu"},
        task_id=task_v11.task_id
    )

    assert res_v11["success"] is True
    assert res_v11["stale_blocked"] is False

    final_state = fsm.get_state()
    assert final_state.fields["postal_code"].value == "600028"
    assert final_state.fields["postal_code"].validation_details["city"] == "Chennai"
