from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class FieldStatus(str, Enum):
    EMPTY = "EMPTY"
    ACTIVE = "ACTIVE"
    PROCESSING = "PROCESSING"
    VALIDATING = "VALIDATING"
    CONFIRMED = "CONFIRMED"
    SKIPPED = "SKIPPED"
    STALE_RESULT_BLOCKED = "STALE_RESULT_BLOCKED"

class ValidationStatus(str, Enum):
    UNVALIDATED = "UNVALIDATED"
    VALIDATING = "VALIDATING"
    VALID = "VALID"
    INVALID = "INVALID"
    STALE_BLOCKED = "STALE_BLOCKED"

class FormFieldValue(BaseModel):
    name: str
    label: str
    value: str = ""
    status: FieldStatus = FieldStatus.EMPTY
    validation_status: ValidationStatus = ValidationStatus.UNVALIDATED
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    interaction_version: int = 0
    error_message: Optional[str] = None
    validation_details: Optional[Dict[str, Any]] = None

class FormState(BaseModel):
    fields: Dict[str, FormFieldValue] = Field(default_factory=dict)
    active_field_key: str = "full_name"
    last_updated_version: int = 0

    @classmethod
    def create_initial(cls) -> "FormState":
        default_fields = {
            "full_name": FormFieldValue(name="full_name", label="Full Name", status=FieldStatus.ACTIVE),
            "date_of_birth": FormFieldValue(name="date_of_birth", label="Date of Birth"),
            "phone_number": FormFieldValue(name="phone_number", label="Phone Number"),
            "email": FormFieldValue(name="email", label="Email Address"),
            "address": FormFieldValue(name="address", label="Street Address"),
            "city": FormFieldValue(name="city", label="City"),
            "state": FormFieldValue(name="state", label="State / Province"),
            "postal_code": FormFieldValue(name="postal_code", label="Postal Code"),
            "occupation": FormFieldValue(name="occupation", label="Occupation"),
            "employment_status": FormFieldValue(name="employment_status", label="Employment Status"),
        }
        return cls(fields=default_fields, active_field_key="full_name", last_updated_version=0)
