import asyncio
import uuid
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from backend.app.models.conversation_models import (
    UserIntent,
    StructuredAction,
    ConversationMessage,
    EventLog
)
from backend.app.models.form_models import FormState, FieldStatus, ValidationStatus
from backend.app.services.interaction_version_manager import InteractionVersionManager
from backend.app.services.form_state_manager import FormStateManager
from backend.app.services.task_manager import TaskManager
from backend.app.services.stale_result_guard import StaleResultGuard
from backend.app.services.validation_service import ValidationService
from backend.app.services.ai_service import AIService
from backend.app.services.action_validator import ActionValidator
from backend.app.services.speech_service import SpeechService

FIELD_SEQUENCE = [
    "full_name",
    "date_of_birth",
    "phone_number",
    "email",
    "address",
    "city",
    "state",
    "postal_code",
    "occupation",
    "employment_status"
]

class ConversationService:
    """
    Orchestrates the entire Natural Language Form Control pipeline.
    Ensures strict version fencing, uncorrupted state transitions, and background validation continuity.
    """
    def __init__(
        self,
        version_manager: InteractionVersionManager,
        form_state_manager: FormStateManager,
        task_manager: TaskManager,
        stale_guard: StaleResultGuard,
        validation_service: ValidationService,
        ai_service: AIService,
        action_validator: Optional[ActionValidator] = None,
        speech_service: Optional[SpeechService] = None,
        broadcast_fn: Optional[Callable[[Dict[str, Any]], Any]] = None,
        timeline_ref: Optional[List[Dict[str, Any]]] = None
    ):
        self.version_manager = version_manager
        self.form_state_manager = form_state_manager
        self.task_manager = task_manager
        self.stale_guard = stale_guard
        self.validation_service = validation_service
        self.ai_service = ai_service
        self.action_validator = action_validator or ActionValidator()
        self.speech_service = speech_service
        self.broadcast_fn = broadcast_fn
        self.timeline: List[Dict[str, Any]] = timeline_ref if timeline_ref is not None else []
        self.messages: List[ConversationMessage] = []
        self._lock = asyncio.Lock()

    async def _emit_event(
        self,
        event_type: str,
        interaction_version: int,
        active_version: int,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        is_stale_blocked: bool = False
    ) -> Dict[str, Any]:
        """Emits a version-tagged structured event to the timeline and WebSocket clients."""
        event = {
            "id": f"evt_{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "interaction_version": interaction_version,
            "active_version": active_version,
            "message": message,
            "details": details or {},
            "is_stale_blocked": is_stale_blocked
        }
        self.timeline.append(event)
        if self.broadcast_fn:
            try:
                res = self.broadcast_fn({
                    "event": "structured_event",
                    "payload": event
                })
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
            except Exception:
                pass
        return event

    def _get_next_field(self, current_field: str) -> str:
        """Determines the next uncompleted field in the sequence."""
        try:
            curr_idx = FIELD_SEQUENCE.index(current_field)
            state = self.form_state_manager.get_state()
            for next_f in FIELD_SEQUENCE[curr_idx + 1:]:
                field_obj = state.fields.get(next_f)
                if field_obj and field_obj.status in (FieldStatus.EMPTY, FieldStatus.ACTIVE):
                    return next_f
            return current_field
        except ValueError:
            return FIELD_SEQUENCE[0]

    def _generate_authoritative_summary(self) -> str:
        """
        Generates the form summary strictly from authoritative server-side FormStateManager data.
        Does not allow LLM hallucination or invention of state values.
        """
        state = self.form_state_manager.get_state()
        provided = []
        skipped = []
        remaining = []

        for f_name in FIELD_SEQUENCE:
            f_obj = state.fields.get(f_name)
            if not f_obj:
                continue
            lbl = f_obj.label
            if f_obj.value and f_obj.status in (FieldStatus.CONFIRMED, FieldStatus.VALIDATING, FieldStatus.ACTIVE):
                val_extra = f" ({f_obj.validation_status.value})" if f_obj.validation_status != ValidationStatus.UNVALIDATED else ""
                provided.append(f"{lbl}: {f_obj.value}{val_extra}")
            elif f_obj.status == FieldStatus.SKIPPED:
                skipped.append(lbl)
            else:
                remaining.append(lbl)

        summary_parts = []
        if provided:
            summary_parts.append(f"Completed details ({len(provided)}): " + ", ".join(provided) + ".")
        else:
            summary_parts.append("No fields have been completed yet.")

        if skipped:
            summary_parts.append(f"Skipped ({len(skipped)}): " + ", ".join(skipped) + ".")

        if remaining:
            summary_parts.append(f"Remaining to fill ({len(remaining)}): " + ", ".join(remaining[:3]) + ("..." if len(remaining) > 3 else "") + ".")
        else:
            summary_parts.append("All form fields are complete!")

        return " ".join(summary_parts)

    async def process_user_input(
        self,
        text: str,
        input_source: str = "text",
        interaction_version: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Main natural language processing pipeline with strict version fencing:
        1. Create new interaction version (or verify version if pre-established by voice barge-in).
        2. Emit USER_INPUT_RECEIVED / VOICE_INTERACTION_ACCEPTED / FINAL_TRANSCRIPT_RECEIVED.
        3. Register and call AI interpretation.
        4. Check version fence.
        5. Validate structured action via ActionValidator.
        6. Check version fence again.
        7. Apply action to authoritative FormStateManager.
        8. If postal code, spawn background validation without blocking conversation.
        """
        clean_text = text.strip()
        if not clean_text:
            return {
                "error": "Empty input text",
                "interaction_version": self.version_manager.active_version
            }

        # 1. Handle interaction versioning
        if interaction_version is not None and interaction_version == self.version_manager.active_version:
            req_version = interaction_version
        else:
            req_version = await self.version_manager.create_new_version(
                reason=f"User {input_source} input: '{clean_text}'"
            )
        active_ver = self.version_manager.active_version

        # 2. Emit Input & Voice Lifecycle Events
        if input_source == "voice":
            await self._emit_event(
                event_type="VOICE_INTERACTION_ACCEPTED",
                interaction_version=req_version,
                active_version=active_ver,
                message=f"Voice interaction accepted for v{req_version}",
                details={"input_source": "voice"}
            )
            await self._emit_event(
                event_type="FINAL_TRANSCRIPT_RECEIVED",
                interaction_version=req_version,
                active_version=active_ver,
                message=f"Final transcript received: \"{clean_text}\"",
                details={"transcript": clean_text}
            )
            await self._emit_event(
                event_type="TRANSCRIPT_SUBMITTED",
                interaction_version=req_version,
                active_version=active_ver,
                message=f"Voice transcript submitted to conversation pipeline (v{req_version})",
                details={"transcript": clean_text}
            )

        await self._emit_event(
            event_type="USER_INPUT_RECEIVED",
            interaction_version=req_version,
            active_version=active_ver,
            message=f"User {input_source} input received: \"{clean_text}\"",
            details={"text": clean_text, "input_source": input_source}
        )

        user_msg = ConversationMessage(
            id=f"msg_{uuid.uuid4().hex[:8]}",
            role="user",
            text=clean_text,
            interaction_version=req_version,
            active_version=active_ver
        )
        self.messages.append(user_msg)

        # 3. Context gathering
        current_state = self.form_state_manager.get_state()
        context = {
            "active_field_key": current_state.active_field_key,
            "fields": {k: v.value for k, v in current_state.fields.items()},
            "skipped_fields": [k for k, v in current_state.fields.items() if v.status == FieldStatus.SKIPPED]
        }

        # 4. Emit AI_REQUEST_STARTED
        await self._emit_event(
            event_type="AI_REQUEST_STARTED",
            interaction_version=req_version,
            active_version=self.version_manager.active_version,
            message=f"Gemini interpretation started for v{req_version}",
            details={"input_text": clean_text, "context": context}
        )

        ai_task_id = f"ai_task_{req_version}_{uuid.uuid4().hex[:6]}"

        # 5. Call AI Service
        try:
            raw_ai_action = await self.ai_service.interpret_input(
                text=clean_text,
                context=context,
                interaction_version=req_version,
                task_id=ai_task_id
            )
        except asyncio.CancelledError:
            active_now = self.version_manager.active_version
            await self._emit_event(
                event_type="AI_RESPONSE_REJECTED_STALE",
                interaction_version=req_version,
                active_version=active_now,
                message=f"AI RESULT BLOCKED AS STALE: Request v{req_version} cancelled (superseded by v{active_now})",
                details={"reason": "asyncio_cancelled"},
                is_stale_blocked=True
            )
            return {
                "success": False,
                "is_stale": True,
                "interaction_version": req_version,
                "active_version": active_now,
                "message": f"AI task for version {req_version} was cancelled"
            }

        # 6. Version Fence Check 1: Check if newer user input arrived while AI was thinking
        active_after_ai = self.version_manager.active_version
        if req_version != active_after_ai:
            await self._emit_event(
                event_type="AI_RESPONSE_REJECTED_STALE",
                interaction_version=req_version,
                active_version=active_after_ai,
                message=f"AI RESULT BLOCKED AS STALE: Result for v{req_version} discarded (Active: v{active_after_ai})",
                details={"raw_action": raw_ai_action},
                is_stale_blocked=True
            )
            await self.task_manager.mark_stale_blocked(ai_task_id)
            return {
                "success": False,
                "is_stale": True,
                "interaction_version": req_version,
                "active_version": active_after_ai,
                "message": f"Stale AI result for v{req_version} discarded"
            }

        # AI response accepted as fresh
        await self._emit_event(
            event_type="AI_RESPONSE_RECEIVED",
            interaction_version=req_version,
            active_version=active_after_ai,
            message=f"Gemini returned structured action for v{req_version}",
            details={"raw_action": raw_ai_action}
        )

        # 7. Action Validation Layer
        await self._emit_event(
            event_type="ACTION_VALIDATION_STARTED",
            interaction_version=req_version,
            active_version=active_after_ai,
            message="Validating AI structured action schema and field boundaries"
        )

        validated_action = self.action_validator.validate(raw_ai_action, context)

        if not validated_action.is_valid:
            await self._emit_event(
                event_type="ACTION_REJECTED",
                interaction_version=req_version,
                active_version=self.version_manager.active_version,
                message=f"Action validation rejected: {validated_action.validation_error}",
                details={"error": validated_action.validation_error}
            )
        else:
            await self._emit_event(
                event_type="ACTION_VALIDATED",
                interaction_version=req_version,
                active_version=self.version_manager.active_version,
                message=f"Action validated successfully: {validated_action.action.value}",
                details={"validated_action": validated_action.model_dump()}
            )

        # 8. Version Fence Check 2: Check before state mutation
        if req_version != self.version_manager.active_version:
            active_ver_now = self.version_manager.active_version
            await self._emit_event(
                event_type="AI_RESPONSE_REJECTED_STALE",
                interaction_version=req_version,
                active_version=active_ver_now,
                message=f"AI RESULT BLOCKED AS STALE: Version v{req_version} superseded before state mutation (Active: v{active_ver_now})",
                is_stale_blocked=True
            )
            return {
                "success": False,
                "is_stale": True,
                "interaction_version": req_version,
                "active_version": active_ver_now
            }

        # 9. Apply Action to Form State
        final_response_text = validated_action.response_text

        if validated_action.action == UserIntent.GET_FORM_SUMMARY:
            final_response_text = self._generate_authoritative_summary()
            validated_action.response_text = final_response_text
            await self._emit_event(
                event_type="ACTION_APPLIED",
                interaction_version=req_version,
                active_version=self.version_manager.active_version,
                message="Form summary generated from authoritative server state",
                details={"summary": final_response_text}
            )

        elif validated_action.action in (UserIntent.UPDATE_FIELD, UserIntent.CORRECT_FIELD):
            target = validated_action.target_field
            val = validated_action.value or ""
            if target:
                is_postal = (target == "postal_code")
                initial_status = FieldStatus.VALIDATING if is_postal else FieldStatus.CONFIRMED
                val_status = ValidationStatus.VALIDATING if is_postal else ValidationStatus.UNVALIDATED

                # Update provisional field value
                apply_res = await self.form_state_manager.update_field(
                    field_name=target,
                    value=val,
                    version=req_version,
                    status=initial_status,
                    validation_status=val_status,
                    task_id=ai_task_id
                )

                if apply_res.get("stale_blocked"):
                    return {
                        "success": False,
                        "is_stale": True,
                        "interaction_version": req_version,
                        "active_version": self.version_manager.active_version
                    }

                # Advance active field pointer
                next_f = self._get_next_field(target)
                await self.form_state_manager.set_active_field(next_f)

                await self._emit_event(
                    event_type="ACTION_APPLIED",
                    interaction_version=req_version,
                    active_version=self.version_manager.active_version,
                    message=f"Form state updated: {target} = \"{val}\" (v{req_version})",
                    details={"field": target, "value": val, "status": initial_status.value}
                )

                # Background validation continuity (e.g. Postal Code)
                if is_postal:
                    # Spawn async background validation without blocking the conversation
                    asyncio.create_task(self._run_async_postal_validation(val, req_version))

        elif validated_action.action == UserIntent.SKIP_FIELD:
            target = validated_action.target_field
            if target:
                await self.form_state_manager.skip_field(target, req_version, task_id=ai_task_id)
                next_f = self._get_next_field(target)
                await self.form_state_manager.set_active_field(next_f)
                await self._emit_event(
                    event_type="ACTION_APPLIED",
                    interaction_version=req_version,
                    active_version=self.version_manager.active_version,
                    message=f"Field '{target}' skipped (v{req_version})",
                    details={"field": target}
                )

        elif validated_action.action == UserIntent.NAVIGATE_FIELD:
            target = validated_action.target_field
            if target:
                await self.form_state_manager.set_active_field(target)
                await self._emit_event(
                    event_type="ACTION_APPLIED",
                    interaction_version=req_version,
                    active_version=self.version_manager.active_version,
                    message=f"Navigated active field to '{target}' (v{req_version})",
                    details={"active_field": target}
                )

        elif validated_action.action == UserIntent.REQUEST_CLARIFICATION:
            await self._emit_event(
                event_type="REQUEST_CLARIFICATION",
                interaction_version=req_version,
                active_version=self.version_manager.active_version,
                message=f"Clarification requested: \"{final_response_text}\"",
                details={"reason": validated_action.validation_error or "ambiguous_input"}
            )

        elif validated_action.action in (UserIntent.STOP, UserIntent.CONFIRM):
            await self._emit_event(
                event_type="ACTION_APPLIED",
                interaction_version=req_version,
                active_version=self.version_manager.active_version,
                message=f"Action '{validated_action.action.value}' acknowledged",
                details={"action": validated_action.action.value}
            )

        # 10. Record Assistant Response message
        asst_msg = ConversationMessage(
            id=f"msg_{uuid.uuid4().hex[:8]}",
            role="assistant",
            text=final_response_text,
            interaction_version=req_version,
            active_version=self.version_manager.active_version,
            structured_action=validated_action
        )
        self.messages.append(asst_msg)

        current_form = self.form_state_manager.get_state().model_dump()

        # Broadcast state update to WS clients
        if self.broadcast_fn:
            try:
                res = self.broadcast_fn({
                    "event": "form_state_updated",
                    "interaction_version": req_version,
                    "active_version": self.version_manager.active_version,
                    "form_state": current_form,
                    "message": asst_msg.model_dump()
                })
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
            except Exception:
                pass

        # 11. Trigger Speech Synthesis pipeline (Async, fenced by version)
        if self.speech_service and final_response_text:
            asyncio.create_task(
                self.speech_service.synthesize_response(
                    text=final_response_text,
                    interaction_version=req_version
                )
            )

        return {
            "success": True,
            "is_stale": False,
            "interaction_version": req_version,
            "active_version": self.version_manager.active_version,
            "action": validated_action.model_dump(),
            "response_text": final_response_text,
            "form_state": current_form
        }

    async def _run_async_postal_validation(self, postal_code: str, version: int, uncancellable: bool = True) -> None:
        """
        Runs background postal code validation asynchronously.
        Fenced by StaleResultGuard upon completion to prevent stale results from corrupting state.
        """
        task_id = f"bg_val_postal_{version}_{uuid.uuid4().hex[:6]}"
        curr_task = asyncio.current_task()
        val_task_rec = await self.task_manager.register_task(
            task_id=task_id,
            name=f"bg_validate_postal_{postal_code}",
            version=version,
            target_field="postal_code",
            payload={"postal_code": postal_code},
            uncancellable=uncancellable,
            asyncio_task=curr_task
        )

        await self._emit_event(
            event_type="VALIDATION_STARTED",
            interaction_version=version,
            active_version=self.version_manager.active_version,
            message=f"Background postal validation initiated for '{postal_code}' (v{version})",
            details={"postal_code": postal_code, "task_id": task_id}
        )

        try:
            val_result = await self.validation_service.validate_postal_code(
                postal_code=postal_code,
                custom_delay=0.2
            )
        except asyncio.CancelledError:
            await self._emit_event(
                event_type="TASK_CANCELLED",
                interaction_version=version,
                active_version=self.version_manager.active_version,
                message=f"Validation task {task_id} aborted early on interruption",
                details={"task_id": task_id}
            )
            return

        # Verification & state application via StaleResultGuard
        apply_res = await self.form_state_manager.apply_validation_result(
            field_name="postal_code",
            version=version,
            is_valid=val_result.get("is_valid", False),
            validation_details=val_result,
            error_message=val_result.get("error_message"),
            task_id=task_id
        )

        active_now = self.version_manager.active_version

        if apply_res.get("stale_blocked"):
            await self._emit_event(
                event_type="STALE_RESULT_BLOCKED",
                interaction_version=version,
                active_version=active_now,
                message=f"STALE RESULT BLOCKED: Postal validation for '{postal_code}' (v{version}) rejected by fence (Active: v{active_now})",
                details={"postal_code": postal_code, "task_id": task_id},
                is_stale_blocked=True
            )
        else:
            await self._emit_event(
                event_type="VALIDATION_RESULT_ACCEPTED",
                interaction_version=version,
                active_version=active_now,
                message=f"Validation accepted: Postal code '{postal_code}' confirmed valid",
                details=val_result
            )

    def get_history(self) -> List[Dict[str, Any]]:
        return [m.model_dump() for m in self.messages]

    def reset(self) -> None:
        self.messages.clear()
