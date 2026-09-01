import asyncio
import uuid
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

from backend.app.models.form_models import FieldStatus, ValidationStatus
from backend.app.models.conversation_models import EventLog
from backend.app.services.interaction_version_manager import InteractionVersionManager
from backend.app.services.task_manager import TaskManager
from backend.app.services.stale_result_guard import StaleResultGuard
from backend.app.services.form_state_manager import FormStateManager
from backend.app.services.validation_service import ValidationService

class StressTestService:
    """
    Deterministic stress test engine demonstrating the core race condition:
    User input -> Validation start (with configurable delay) -> User interruption ->
    Version bump -> Invalidation/Cancellation -> Stale result fencing -> New result acceptance.
    """
    def __init__(
        self,
        version_manager: InteractionVersionManager,
        task_manager: TaskManager,
        stale_guard: StaleResultGuard,
        form_state_manager: FormStateManager,
        validation_service: ValidationService,
        broadcast_fn: Optional[Callable[[Dict[str, Any]], Any]] = None
    ):
        self.version_manager = version_manager
        self.task_manager = task_manager
        self.stale_guard = stale_guard
        self.form_state_manager = form_state_manager
        self.validation_service = validation_service
        self.broadcast_fn = broadcast_fn
        self.event_timeline: List[Dict[str, Any]] = []
        self._is_running: bool = False

    async def log_event(
        self,
        event_type: str,
        interaction_version: int,
        active_version: int,
        message: str,
        task_id: Optional[str] = None,
        is_stale_blocked: bool = False,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Records an event into the structured timeline and broadcasts to WebSocket subscribers."""
        evt = {
            "event_id": f"evt_{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "interaction_version": interaction_version,
            "active_version": active_version,
            "task_id": task_id,
            "message": message,
            "is_stale_blocked": is_stale_blocked,
            "details": details or {}
        }
        self.event_timeline.append(evt)

        if self.broadcast_fn:
            try:
                res = self.broadcast_fn({
                    "event": "stress_test_event",
                    "payload": evt,
                    "active_version": active_version,
                    "form_state": self.form_state_manager.get_state().model_dump(),
                    "stale_blocks_count": self.stale_guard.stale_blocks_count
                })
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass

        return evt

    def reset_session(self, initial_version: int = 10) -> None:
        """Resets all session state cleanly to guarantee no leakage between test runs."""
        self.version_manager.reset(initial_version=initial_version)
        self.task_manager.reset()
        self.stale_guard.reset()
        self.form_state_manager.reset()
        self.event_timeline.clear()
        self._is_running = False

    async def run_stress_test(
        self,
        mode: str = "uncancellable",
        old_postal_code: str = "600001",
        new_postal_code: str = "600028",
        validation_delay_seconds: float = 3.0,
        interrupt_after_seconds: float = 1.0,
        reset_before_run: bool = True
    ) -> Dict[str, Any]:
        """
        Executes a deterministic stress test showing state correctness under race condition.
        Mode 'cancellable': The old validation task is cancelled when the user interrupts.
        Mode 'uncancellable': The old validation task continues in background, completes,
        and its result is safely blocked by the StaleResultGuard.
        """
        if reset_before_run:
            self.reset_session()

        test_run_id = f"run_{uuid.uuid4().hex[:8]}"
        is_uncancellable = (mode.lower() == "uncancellable")
        self._is_running = True

        # STEP 1: First User Request
        v1 = await self.version_manager.create_new_version(reason=f"User provided postal code {old_postal_code}")
        await self.log_event(
            event_type="INTERACTION_STARTED",
            interaction_version=v1,
            active_version=v1,
            message=f"Interaction started for Request 1 (Version {v1})"
        )

        await self.log_event(
            event_type="USER_INPUT_RECEIVED",
            interaction_version=v1,
            active_version=v1,
            message=f'User: "My postal code is {old_postal_code}"',
            details={"input": old_postal_code, "field": "postal_code"}
        )

        # Set field to VALIDATING
        await self.form_state_manager.update_field(
            field_name="postal_code",
            value=old_postal_code,
            version=v1,
            status=FieldStatus.VALIDATING,
            validation_status=ValidationStatus.VALIDATING
        )
        await self.log_event(
            event_type="FIELD_UPDATED",
            interaction_version=v1,
            active_version=v1,
            message=f"Field 'postal_code' set to {old_postal_code} (Status: VALIDATING)",
            details={"field": "postal_code", "value": old_postal_code, "status": "VALIDATING"}
        )

        # Register Task 1
        t1_record = await self.task_manager.register_task(
            name=f"postal_validation_{old_postal_code}",
            version=v1,
            target_field="postal_code",
            payload={"postal_code": old_postal_code, "delay": validation_delay_seconds},
            uncancellable=is_uncancellable
        )
        t1_id = t1_record.task_id

        await self.log_event(
            event_type="VALIDATION_STARTED",
            interaction_version=v1,
            active_version=v1,
            task_id=t1_id,
            message=f"Validation started for {old_postal_code} [Delay: {validation_delay_seconds}s, Uncancellable: {is_uncancellable}]",
            details={"task_id": t1_id, "delay": validation_delay_seconds, "uncancellable": is_uncancellable}
        )

        # Define Async Worker for Task 1
        t1_completed_event = asyncio.Event()

        async def _t1_worker():
            try:
                # Artificial delay for validation
                val_res = await self.validation_service.validate_postal_code(
                    postal_code=old_postal_code,
                    custom_delay=validation_delay_seconds
                )
                
                await self.log_event(
                    event_type="VALIDATION_RESULT_RETURNED",
                    interaction_version=v1,
                    active_version=self.version_manager.active_version,
                    task_id=t1_id,
                    message=f"Validation returned for {old_postal_code} (Version {v1})",
                    details=val_res
                )

                # Attempt to apply through StaleResultGuard
                apply_res = await self.form_state_manager.apply_validation_result(
                    field_name="postal_code",
                    version=v1,
                    is_valid=val_res["is_valid"],
                    validation_details=val_res,
                    task_id=t1_id
                )

                if apply_res.get("stale_blocked"):
                    await self.log_event(
                        event_type="STALE_RESULT_BLOCKED",
                        interaction_version=v1,
                        active_version=self.version_manager.active_version,
                        task_id=t1_id,
                        is_stale_blocked=True,
                        message=f"STALE RESULT BLOCKED: Result for {old_postal_code} (Version {v1}) rejected by fence (Active: Version {self.version_manager.active_version})",
                        details={"blocked_version": v1, "active_version": self.version_manager.active_version}
                    )
                else:
                    await self.log_event(
                        event_type="VALIDATION_RESULT_ACCEPTED",
                        interaction_version=v1,
                        active_version=self.version_manager.active_version,
                        task_id=t1_id,
                        message=f"Validation result for {old_postal_code} accepted",
                        details=apply_res
                    )
            except asyncio.CancelledError:
                await self.log_event(
                    event_type="TASK_CANCELLED",
                    interaction_version=v1,
                    active_version=self.version_manager.active_version,
                    task_id=t1_id,
                    message=f"Task {t1_id} for Version {v1} successfully cancelled upon interruption",
                    details={"cancelled_version": v1}
                )
            finally:
                t1_completed_event.set()

        t1_async_task = asyncio.create_task(_t1_worker())
        # Attach asyncio handle to task manager
        self.task_manager._asyncio_handles[t1_id] = t1_async_task

        # STEP 2: Wait for interruption trigger
        await asyncio.sleep(interrupt_after_seconds)

        # STEP 3: User Interruption occurs while T1 is in-flight!
        v2 = await self.version_manager.create_new_version(reason=f"User correction: {new_postal_code}")
        
        await self.log_event(
            event_type="INTERRUPTION_DETECTED",
            interaction_version=v2,
            active_version=v2,
            message=f'User Interruption: "Wait, change it to {new_postal_code}"',
            details={"interrupted_by": new_postal_code, "new_version": v2}
        )

        await self.log_event(
            event_type="VERSION_INVALIDATED",
            interaction_version=v1,
            active_version=v2,
            message=f"Version {v1} marked OBSOLETE. Version {v2} is now AUTHORITATIVE.",
            details={"invalidated_version": v1, "active_version": v2}
        )

        await self.log_event(
            event_type="TASK_CANCELLATION_REQUESTED",
            interaction_version=v1,
            active_version=v2,
            task_id=t1_id,
            message=f"Cancellation requested for tasks of Version {v1} (Uncancellable={is_uncancellable})",
            details={"task_id": t1_id, "uncancellable": is_uncancellable}
        )

        # Update field to new value under Version 2
        await self.form_state_manager.update_field(
            field_name="postal_code",
            value=new_postal_code,
            version=v2,
            status=FieldStatus.VALIDATING,
            validation_status=ValidationStatus.VALIDATING
        )
        await self.log_event(
            event_type="FIELD_UPDATED",
            interaction_version=v2,
            active_version=v2,
            message=f"Field 'postal_code' updated to {new_postal_code} (Status: VALIDATING, Version: {v2})",
            details={"field": "postal_code", "value": new_postal_code, "version": v2}
        )

        # Register Task 2 (for new postal code)
        t2_record = await self.task_manager.register_task(
            name=f"postal_validation_{new_postal_code}",
            version=v2,
            target_field="postal_code",
            payload={"postal_code": new_postal_code, "delay": 0.5},
            uncancellable=False
        )
        t2_id = t2_record.task_id

        await self.log_event(
            event_type="VALIDATION_STARTED",
            interaction_version=v2,
            active_version=v2,
            task_id=t2_id,
            message=f"Validation started for {new_postal_code} (Version {v2})",
            details={"task_id": t2_id, "postal_code": new_postal_code}
        )

        t2_completed_event = asyncio.Event()

        async def _t2_worker():
            try:
                # Fast validation for replacement request (0.5s)
                val_res = await self.validation_service.validate_postal_code(
                    postal_code=new_postal_code,
                    custom_delay=0.5
                )

                await self.log_event(
                    event_type="VALIDATION_RESULT_RETURNED",
                    interaction_version=v2,
                    active_version=self.version_manager.active_version,
                    task_id=t2_id,
                    message=f"Validation returned for {new_postal_code} (Version {v2})",
                    details=val_res
                )

                apply_res = await self.form_state_manager.apply_validation_result(
                    field_name="postal_code",
                    version=v2,
                    is_valid=val_res["is_valid"],
                    validation_details=val_res,
                    task_id=t2_id
                )

                if not apply_res.get("stale_blocked"):
                    await self.log_event(
                        event_type="VALIDATION_RESULT_ACCEPTED",
                        interaction_version=v2,
                        active_version=self.version_manager.active_version,
                        task_id=t2_id,
                        message=f"Validation result for {new_postal_code} accepted and confirmed into Form State",
                        details=apply_res
                    )
                    await self.log_event(
                        event_type="FORM_STATE_UPDATED",
                        interaction_version=v2,
                        active_version=self.version_manager.active_version,
                        message=f"Form State Authoritative Value: postal_code = {new_postal_code} (CONFIRMED)",
                        details={"field": "postal_code", "value": new_postal_code, "status": "CONFIRMED"}
                    )
            finally:
                t2_completed_event.set()

        t2_async_task = asyncio.create_task(_t2_worker())
        self.task_manager._asyncio_handles[t2_id] = t2_async_task

        # Wait for all workers to finish execution
        await asyncio.gather(t1_completed_event.wait(), t2_completed_event.wait())
        self._is_running = False

        # Verify final state assertions
        final_form = self.form_state_manager.get_state()
        final_postal_field = final_form.fields["postal_code"]
        
        is_success = (
            final_postal_field.value == new_postal_code and
            final_postal_field.status == FieldStatus.CONFIRMED and
            final_postal_field.interaction_version == v2
        )

        if is_uncancellable:
            # Mode B verification: StaleResultGuard must have recorded at least 1 blocked stale result
            is_success = is_success and (self.stale_guard.stale_blocks_count >= 1)

        return {
            "test_run_id": test_run_id,
            "mode": mode,
            "final_interaction_version": self.version_manager.active_version,
            "final_form_state": final_form.model_dump(),
            "stale_results_blocked": self.stale_guard.stale_blocks_count,
            "cancelled_tasks_count": self.task_manager.get_cancelled_tasks_count(),
            "event_timeline": list(self.event_timeline),
            "test_success": is_success,
            "summary": f"Stress test completed. Mode: {mode}. Final postal code: {final_postal_field.value}. Stale results blocked: {self.stale_guard.stale_blocks_count}."
        }
