import pytest
import asyncio
from backend.app.services.interaction_version_manager import InteractionVersionManager
from backend.app.services.task_manager import TaskManager
from backend.app.services.stale_result_guard import StaleResultGuard
from backend.app.models.task_models import TaskStatus

@pytest.mark.asyncio
async def test_task_cancellation_on_interruption():
    vm = InteractionVersionManager(initial_version=10)
    tm = TaskManager()

    # Wire cancellation listener
    def on_invalidation(old_ver, new_ver):
        asyncio.create_task(tm.cancel_tasks_for_version(old_ver))

    vm.add_invalidation_listener(on_invalidation)

    # Register an async task for version 10
    task_v10 = await tm.register_task(name="llm_inference", version=10, uncancellable=False)
    assert task_v10.status == TaskStatus.ACTIVE

    # Interruption occurs
    await vm.create_new_version(reason="User said Wait")
    await asyncio.sleep(0.05)  # Allow async invalidation task to run

    cancelled_task = tm.get_task(task_v10.task_id)
    assert cancelled_task.status == TaskStatus.CANCELLED
    assert tm.get_cancelled_tasks_count() == 1

@pytest.mark.asyncio
async def test_multiple_rapid_interruptions():
    vm = InteractionVersionManager(initial_version=10)
    tm = TaskManager()
    guard = StaleResultGuard(version_manager=vm, task_manager=tm)

    # Wire cancellation
    def on_invalidation(old_ver, new_ver):
        asyncio.create_task(tm.cancel_tasks_for_version(old_ver))
    vm.add_invalidation_listener(on_invalidation)

    # User rapidly interrupts 4 times: 10 -> 11 -> 12 -> 13
    t10 = await tm.register_task("task_10", version=10)
    await vm.create_new_version()

    t11 = await tm.register_task("task_11", version=11)
    await vm.create_new_version()

    t12 = await tm.register_task("task_12", version=12)
    await vm.create_new_version()

    t13 = await tm.register_task("task_13", version=13)

    assert vm.active_version == 13

    # All old versions must fail the fence
    assert guard.can_apply_result(10) is False
    assert guard.can_apply_result(11) is False
    assert guard.can_apply_result(12) is False
    assert guard.can_apply_result(13) is True

@pytest.mark.asyncio
async def test_uncancellable_task_fencing():
    """
    Simulates a 3rd-party HTTP request or uncancellable computation.
    Even though the task cannot be cancelled and runs to completion,
    the version fence guarantees its result is discarded.
    """
    vm = InteractionVersionManager(initial_version=10)
    tm = TaskManager()
    guard = StaleResultGuard(version_manager=vm, task_manager=tm)

    # Register an uncancellable task
    t_uncancellable = await tm.register_task(
        name="external_slow_api",
        version=10,
        uncancellable=True
    )

    # User interrupts while slow API is in flight
    await vm.create_new_version(reason="Interruption during external call")

    # Try cancelling version 10 - uncancellable task remains running
    cancelled = await tm.cancel_tasks_for_version(10)
    assert len(cancelled) == 0  # Was not cancelled because uncancellable=True

    # Slow API completes and attempts to apply its output
    state_mutated = False
    def apply_mutation():
        nonlocal state_mutated
        state_mutated = True

    res = await guard.verify_and_apply(
        operation_version=10,
        task_id=t_uncancellable.task_id,
        task_name="external_slow_api",
        apply_fn=apply_mutation
    )

    assert res["stale_blocked"] is True
    assert state_mutated is False  # Correctness guarantee held!
    assert guard.stale_blocks_count == 1
