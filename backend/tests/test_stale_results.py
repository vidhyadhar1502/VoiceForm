import pytest
import asyncio
from backend.app.services.interaction_version_manager import InteractionVersionManager
from backend.app.services.task_manager import TaskManager
from backend.app.services.stale_result_guard import StaleResultGuard
from backend.app.models.task_models import TaskStatus

@pytest.mark.asyncio
async def test_fresh_result_accepted():
    vm = InteractionVersionManager(initial_version=10)
    tm = TaskManager()
    guard = StaleResultGuard(version_manager=vm, task_manager=tm)

    task = await tm.register_task(name="postal_validation", version=10)
    
    applied_value = None
    def apply_fn():
        nonlocal applied_value
        applied_value = "Chennai, Tamil Nadu"
        return applied_value

    res = await guard.verify_and_apply(
        operation_version=10,
        task_id=task.task_id,
        task_name="postal_validation",
        apply_fn=apply_fn
    )

    assert res["success"] is True
    assert res["stale_blocked"] is False
    assert applied_value == "Chennai, Tamil Nadu"
    assert guard.stale_blocks_count == 0

    updated_task = tm.get_task(task.task_id)
    assert updated_task.status == TaskStatus.COMPLETED

@pytest.mark.asyncio
async def test_stale_result_rejected():
    vm = InteractionVersionManager(initial_version=10)
    tm = TaskManager()
    guard = StaleResultGuard(version_manager=vm, task_manager=tm)

    # Register task for version 10
    task_v10 = await tm.register_task(name="postal_validation_v10", version=10)

    # User interrupts, bumping version to 11
    await vm.create_new_version(reason="User correction")
    assert vm.active_version == 11

    applied_value = None
    def apply_fn():
        nonlocal applied_value
        applied_value = "Stale Value Should Never Apply"
        return applied_value

    # Stale version 10 attempts to return
    res = await guard.verify_and_apply(
        operation_version=10,
        task_id=task_v10.task_id,
        task_name="postal_validation_v10",
        apply_fn=apply_fn
    )

    assert res["success"] is False
    assert res["stale_blocked"] is True
    assert applied_value is None  # Mutation was fenced and not executed!
    assert guard.stale_blocks_count == 1

    updated_task = tm.get_task(task_v10.task_id)
    assert updated_task.status == TaskStatus.STALE_BLOCKED
