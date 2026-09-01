from typing import Dict, Any, Optional
from backend.app.models.conversation_models import UserIntent, StructuredAction
from backend.app.services.ai_provider import VALID_FIELDS

class ActionValidator:
    """
    Validation layer for untrusted LLM outputs.
    Ensures action types, target field names, values, and flags adhere to schema constraints.
    Rejects malformed outputs and unknown fields by transforming them to REQUEST_CLARIFICATION.
    """
    def __init__(self, allowed_fields=None):
        self.allowed_fields = set(allowed_fields or VALID_FIELDS)

    def validate(self, raw_action: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> StructuredAction:
        """
        Validates raw dictionary from AI output.
        Returns a sanitized StructuredAction. If invalid, returns a REQUEST_CLARIFICATION action.
        """
        if not isinstance(raw_action, dict):
            return StructuredAction(
                action=UserIntent.REQUEST_CLARIFICATION,
                target_field=None,
                value=None,
                requires_validation=False,
                response_text="I couldn't process that response format. Could you please clarify your request?",
                is_valid=False,
                validation_error="AI output is not a JSON dictionary"
            )

        # 1. Action Type Validation
        raw_action_str = str(raw_action.get("action") or raw_action.get("intent") or "REQUEST_CLARIFICATION").upper()
        try:
            action_intent = UserIntent(raw_action_str)
        except ValueError:
            return StructuredAction(
                action=UserIntent.REQUEST_CLARIFICATION,
                target_field=None,
                value=None,
                requires_validation=False,
                response_text=f"I didn't recognize that action '{raw_action_str}'. How can I help with your form?",
                is_valid=False,
                validation_error=f"Unknown action type: '{raw_action_str}'"
            )

        target_field = raw_action.get("target_field")
        value = raw_action.get("value")
        response_text = raw_action.get("response_text", "")
        requires_validation = bool(raw_action.get("requires_validation", False))

        # 2. Field-level validation for actions that target a specific field
        if action_intent in (UserIntent.UPDATE_FIELD, UserIntent.CORRECT_FIELD, UserIntent.SKIP_FIELD, UserIntent.NAVIGATE_FIELD):
            if not target_field:
                # If target field is missing for UPDATE/CORRECT/SKIP/NAVIGATE
                return StructuredAction(
                    action=UserIntent.REQUEST_CLARIFICATION,
                    target_field=None,
                    value=None,
                    requires_validation=False,
                    response_text="Which form field would you like to update or navigate to?",
                    is_valid=False,
                    validation_error="Missing target_field for field-specific action"
                )

            # Check unknown fields
            clean_field = str(target_field).lower().strip()
            if clean_field not in self.allowed_fields:
                allowed_list_str = ", ".join([f.replace("_", " ") for f in list(self.allowed_fields)[:5]])
                return StructuredAction(
                    action=UserIntent.REQUEST_CLARIFICATION,
                    target_field=clean_field,
                    value=None,
                    requires_validation=False,
                    response_text=f"I didn't recognize the field '{clean_field}'. Please choose from valid fields like {allowed_list_str}.",
                    is_valid=False,
                    validation_error=f"Unknown target_field: '{clean_field}'"
                )

            target_field = clean_field

            # For postal_code, enforce requires_validation=True
            if target_field == "postal_code":
                requires_validation = True

            # If value is present, cast to string safely
            if value is not None:
                value = str(value).strip()

        # Generate default friendly response text if empty
        if not response_text:
            if action_intent == UserIntent.UPDATE_FIELD and target_field:
                response_text = f"I've updated your {target_field.replace('_', ' ')}."
            elif action_intent == UserIntent.CORRECT_FIELD and target_field:
                response_text = f"I've changed your {target_field.replace('_', ' ')} to {value}."
            elif action_intent == UserIntent.SKIP_FIELD and target_field:
                response_text = f"I've skipped {target_field.replace('_', ' ')} for now."
            elif action_intent == UserIntent.NAVIGATE_FIELD and target_field:
                response_text = f"Navigating to {target_field.replace('_', ' ')}."
            elif action_intent == UserIntent.GET_FORM_SUMMARY:
                response_text = "Here is your form summary."
            elif action_intent == UserIntent.STOP:
                response_text = "I've paused the form."
            elif action_intent == UserIntent.CONFIRM:
                response_text = "Form details confirmed."
            else:
                response_text = "Understood."

        return StructuredAction(
            action=action_intent,
            intent=action_intent,
            target_field=target_field,
            value=value,
            requires_validation=requires_validation,
            response_text=response_text,
            is_valid=True,
            validation_error=None
        )
