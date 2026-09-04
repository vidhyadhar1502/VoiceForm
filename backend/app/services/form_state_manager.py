import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
from backend.app.models.form_models import FormState, FormFieldValue, FieldStatus, ValidationStatus
from backend.app.services.stale_result_guard import StaleResultGuard

class FormStateManager:
    """
    Authoritative state manager for the 10-field VoiceForm.
    All state mutations are fenced by the StaleResultGuard to ensure older
    asynchronous operations never overwrite newer user inputs.
    """
    def __init__(self, stale_guard: StaleResultGuard):
        self._state: FormState = FormState.create_initial()
        self._stale_guard: StaleResultGuard = stale_guard
        self._lock: asyncio.Lock = asyncio.Lock()

    def get_state(self) -> FormState:
        return self._state.model_copy(deep=True)

    async def update_field(
        self,
        field_name: str,
        value: str,
        version: int,
        status: FieldStatus = FieldStatus.CONFIRMED,
        validation_status: ValidationStatus = ValidationStatus.UNVALIDATED,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Updates a field value strictly through the version fence."""
        async def _apply():
            async with self._lock:
                if field_name not in self._state.fields:
                    raise KeyError(f"Field '{field_name}' not found in form state")
                
                field = self._state.fields[field_name]
                field.value = value
                field.status = status
                field.validation_status = validation_status
                field.updated_at = datetime.utcnow().isoformat()
                field.interaction_version = version
                field.error_message = None
                self._state.last_updated_version = version
                return self._state.model_copy(deep=True).model_dump()

        return await self._stale_guard.verify_and_apply(
            operation_version=version,
            task_id=task_id,
            task_name=f"update_field_{field_name}",
            apply_fn=_apply,
            payload_details={"field": field_name, "value": value}
        )

    async def set_field_validating(
        self,
        field_name: str,
        version: int,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Sets field status to VALIDATING under the version fence."""
        async def _apply():
            async with self._lock:
                if field_name in self._state.fields:
                    field = self._state.fields[field_name]
                    field.status = FieldStatus.VALIDATING
                    field.validation_status = ValidationStatus.VALIDATING
                    field.interaction_version = version
                    return self._state.model_copy(deep=True).model_dump()
        
        return await self._stale_guard.verify_and_apply(
            operation_version=version,
            task_id=task_id,
            task_name=f"validating_{field_name}",
            apply_fn=_apply,
            payload_details={"field": field_name}
        )

    async def apply_validation_result(
        self,
        field_name: str,
        version: int,
        is_valid: bool,
        validation_details: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Applies a background validation tool result. If stale, the guard rejects it,
        preventing outdated tool executions from overriding newer inputs.
        """
        async def _apply():
            async with self._lock:
                if field_name not in self._state.fields:
                    return None
                field = self._state.fields[field_name]
                field.status = FieldStatus.CONFIRMED if is_valid else FieldStatus.ACTIVE
                field.validation_status = ValidationStatus.VALID if is_valid else ValidationStatus.INVALID
                field.validation_details = validation_details
                field.error_message = error_message
                field.updated_at = datetime.utcnow().isoformat()
                return self._state.model_copy(deep=True).model_dump()

        return await self._stale_guard.verify_and_apply(
            operation_version=version,
            task_id=task_id,
            task_name=f"apply_validation_{field_name}",
            apply_fn=_apply,
            payload_details={"field": field_name, "is_valid": is_valid, "details": validation_details}
        )

    async def skip_field(self, field_name: str, version: int, task_id: Optional[str] = None) -> Dict[str, Any]:
        """Marks a field as SKIPPED under the version fence."""
        async def _apply():
            async with self._lock:
                if field_name in self._state.fields:
                    field = self._state.fields[field_name]
                    field.status = FieldStatus.SKIPPED
                    field.updated_at = datetime.utcnow().isoformat()
                    field.interaction_version = version
                    return self._state.model_copy(deep=True).model_dump()

        return await self._stale_guard.verify_and_apply(
            operation_version=version,
            task_id=task_id,
            task_name=f"skip_field_{field_name}",
            apply_fn=_apply,
            payload_details={"field": field_name}
        )

    async def set_active_field(self, field_name: str) -> None:
        async with self._lock:
            if field_name in self._state.fields:
                self._state.active_field_key = field_name

    def reset(self) -> None:
        self._state = FormState.create_initial()

    def get_field_value(self, field_name: str) -> Optional[str]:
        if field_name in self._state.fields:
            return self._state.fields[field_name].value
        return None

    def get_field_status(self, field_name: str) -> Optional[FieldStatus]:
        if field_name in self._state.fields:
            return self._state.fields[field_name].status
        return None
