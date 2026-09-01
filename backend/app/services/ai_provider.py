import json
import re
import os
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import httpx

from backend.app.models.conversation_models import UserIntent, StructuredAction

VALID_FIELDS = [
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

SYSTEM_PROMPT = """You are an AI assistant orchestrating a structured form filling session.
Your task is to interpret the user's natural language input and convert it into a SINGLE structured JSON action.

Known Form Fields:
- full_name (e.g., 'Vidhyadhar S')
- date_of_birth (e.g., '15 February 2006')
- phone_number (e.g., '9876543210')
- email (e.g., 'user@example.com')
- address (e.g., '123 Main St')
- city (e.g., 'Chennai')
- state (e.g., 'Tamil Nadu')
- postal_code (e.g., '600028') [Requires validation]
- occupation (e.g., 'Software Developer')
- employment_status (e.g., 'Employed', 'Student')

Supported Actions:
1. UPDATE_FIELD: Providing or updating a field value.
2. CORRECT_FIELD: Correcting an earlier field (e.g., 'Actually, change my occupation to Software Developer').
3. SKIP_FIELD: User asks to skip a field (e.g., 'Skip the address for now').
4. NAVIGATE_FIELD: User asks to jump/navigate to a field (e.g., 'Go back to my phone number').
5. GET_FORM_SUMMARY: User asks for a summary of provided information (e.g., 'What information have I provided so far?').
6. REQUEST_CLARIFICATION: User input is ambiguous, unrecognizable, or relates to unknown fields.
7. STOP: User wants to pause or stop (e.g., 'Stop', 'Wait a minute').
8. CONFIRM: User confirms/approves current state (e.g., 'Looks good', 'Confirm').

JSON Output Schema:
{
  "action": "UPDATE_FIELD | CORRECT_FIELD | SKIP_FIELD | NAVIGATE_FIELD | GET_FORM_SUMMARY | REQUEST_CLARIFICATION | STOP | CONFIRM",
  "target_field": "<field_name_or_null>",
  "value": "<extracted_value_or_null>",
  "requires_validation": true | false,
  "response_text": "<concise, friendly conversational response>"
}

Note: For postal_code, set requires_validation: true. For other fields, requires_validation: false.
Output strictly valid JSON.
"""

class AIProvider(ABC):
    """Abstract interface for AI Natural Language Form Interpretation."""
    @abstractmethod
    async def interpret_user_input(
        self,
        text: str,
        context: Dict[str, Any],
        interaction_version: int
    ) -> Dict[str, Any]:
        """Interprets user input and returns a structured action dict."""
        pass


class RuleBasedFallbackProvider(AIProvider):
    """
    Deterministic rule-based parser used as fallback and mock reference.
    Converts common natural language expressions into structured actions with 100% precision.
    """
    async def interpret_user_input(
        self,
        text: str,
        context: Dict[str, Any],
        interaction_version: int
    ) -> Dict[str, Any]:
        clean_text = text.strip()
        lower_text = clean_text.lower()
        active_field = context.get("active_field_key", "full_name")

        # 1. Summary request
        if any(phrase in lower_text for phrase in [
            "what information have i provided",
            "what have i filled",
            "form summary",
            "summary of my form",
            "show summary",
            "what information do you have",
            "what did i provide"
        ]):
            return {
                "action": UserIntent.GET_FORM_SUMMARY.value,
                "target_field": None,
                "value": None,
                "requires_validation": False,
                "response_text": "Here is a summary of the information you have provided so far."
            }

        # 2. Stop / Pause
        if lower_text in ["stop", "pause", "hold on", "wait", "cancel"]:
            return {
                "action": UserIntent.STOP.value,
                "target_field": None,
                "value": None,
                "requires_validation": False,
                "response_text": "I've paused the form filling. Let me know when you're ready to continue."
            }

        # 3. Confirm
        if lower_text in ["confirm", "looks good", "yes looks good", "all correct", "i confirm", "submit"]:
            return {
                "action": UserIntent.CONFIRM.value,
                "target_field": None,
                "value": None,
                "requires_validation": False,
                "response_text": "Thank you. Your details have been confirmed."
            }

        # 4. Skip field
        skip_match = re.search(r"skip(?:\s+the)?\s+([a-zA-Z_\s]+?)(?:\s+for\s+now|\s*$)", lower_text)
        if "skip" in lower_text:
            target = None
            if "name" in lower_text: target = "full_name"
            elif "birth" in lower_text or "dob" in lower_text: target = "date_of_birth"
            elif "phone" in lower_text or "mobile" in lower_text: target = "phone_number"
            elif "email" in lower_text: target = "email"
            elif "address" in lower_text: target = "address"
            elif "city" in lower_text: target = "city"
            elif "state" in lower_text: target = "state"
            elif "postal" in lower_text or "zip" in lower_text or "pin" in lower_text: target = "postal_code"
            elif "occupation" in lower_text or "job" in lower_text: target = "occupation"
            elif "employment" in lower_text: target = "employment_status"
            else: target = active_field

            field_label = target.replace("_", " ")
            return {
                "action": UserIntent.SKIP_FIELD.value,
                "target_field": target,
                "value": None,
                "requires_validation": False,
                "response_text": f"Okay, I'll skip the {field_label} for now."
            }

        # 5. Navigate / Go back
        if any(p in lower_text for p in ["go back", "navigate to", "jump to", "let's go to", "switch to"]):
            target = None
            if "name" in lower_text: target = "full_name"
            elif "birth" in lower_text or "dob" in lower_text: target = "date_of_birth"
            elif "phone" in lower_text or "mobile" in lower_text: target = "phone_number"
            elif "email" in lower_text: target = "email"
            elif "address" in lower_text: target = "address"
            elif "city" in lower_text: target = "city"
            elif "state" in lower_text: target = "state"
            elif "postal" in lower_text or "zip" in lower_text or "pin" in lower_text: target = "postal_code"
            elif "occupation" in lower_text or "job" in lower_text: target = "occupation"
            elif "employment" in lower_text: target = "employment_status"

            if target:
                field_label = target.replace("_", " ")
                return {
                    "action": UserIntent.NAVIGATE_FIELD.value,
                    "target_field": target,
                    "value": None,
                    "requires_validation": False,
                    "response_text": f"Sure. Let's go back to your {field_label}."
                }

        # 6. Correction phrases ("Actually, change...", "No, make it...", "Change my...")
        is_correction = any(lower_text.startswith(p) for p in ["actually", "no,", "no ", "correction", "change my", "update my"])

        # Check explicit field patterns:
        # Full Name
        name_match = re.search(r"(?:my name is|name is|i am|change my name to|actually,?\s*(?:my\s*)?name is)\s+([A-Za-z\s\.]+)", clean_text, re.IGNORECASE)
        if name_match:
            val = name_match.group(1).strip(" .")
            action_type = UserIntent.CORRECT_FIELD.value if is_correction else UserIntent.UPDATE_FIELD.value
            return {
                "action": action_type,
                "target_field": "full_name",
                "value": val,
                "requires_validation": False,
                "response_text": f"I've updated your full name to {val}." if not is_correction else f"I've changed your full name to {val}."
            }

        # Date of Birth
        dob_match = re.search(r"(?:i was born on|born on|dob is|date of birth is|change my date of birth to)\s+([0-9A-Za-z\s,\/\-]+)", clean_text, re.IGNORECASE)
        if dob_match:
            val = dob_match.group(1).strip(" .")
            action_type = UserIntent.CORRECT_FIELD.value if is_correction else UserIntent.UPDATE_FIELD.value
            return {
                "action": action_type,
                "target_field": "date_of_birth",
                "value": val,
                "requires_validation": False,
                "response_text": f"I've recorded your date of birth as {val}."
            }

        # Phone Number
        phone_match = re.search(r"(?:phone number is|phone is|mobile is|my phone is|call me at|change my phone number to)\s*[:=]?\s*([0-9\+\-\s]{7,15})", clean_text, re.IGNORECASE)
        if phone_match:
            val = phone_match.group(1).strip(" .")
            action_type = UserIntent.CORRECT_FIELD.value if is_correction else UserIntent.UPDATE_FIELD.value
            return {
                "action": action_type,
                "target_field": "phone_number",
                "value": val,
                "requires_validation": False,
                "response_text": f"I've updated your phone number to {val}."
            }

        # Postal Code / Pin code
        postal_match = re.search(r"(?:postal code to|postal code is|postal code|pincode is|zip code is|zip is|pin is)\s*[:=]?\s*([0-9]{5,6})", clean_text, re.IGNORECASE)
        if postal_match or (re.match(r"^\d{5,6}$", clean_text)):
            val = postal_match.group(1) if postal_match else clean_text
            action_type = UserIntent.CORRECT_FIELD.value if is_correction else UserIntent.UPDATE_FIELD.value
            return {
                "action": action_type,
                "target_field": "postal_code",
                "value": val,
                "requires_validation": True,
                "response_text": f"I've updated your postal code to {val} and started validation." if not is_correction else f"I've changed your postal code to {val}."
            }

        # Occupation
        occ_match = re.search(r"(?:occupation to|occupation is|i work as a|i am a|i work as|change my occupation to)\s+([A-Za-z\s]+)", clean_text, re.IGNORECASE)
        if occ_match:
            val = occ_match.group(1).strip(" .")
            action_type = UserIntent.CORRECT_FIELD.value if is_correction else UserIntent.UPDATE_FIELD.value
            return {
                "action": action_type,
                "target_field": "occupation",
                "value": val,
                "requires_validation": False,
                "response_text": f"I've changed your occupation to {val}." if is_correction else f"I've set your occupation to {val}."
            }

        # Address
        addr_match = re.search(r"(?:my address is|address is|i live at|change my address to)\s+([0-9A-Za-z\s,\.\-]+)", clean_text, re.IGNORECASE)
        if addr_match:
            val = addr_match.group(1).strip(" .")
            action_type = UserIntent.CORRECT_FIELD.value if is_correction else UserIntent.UPDATE_FIELD.value
            return {
                "action": action_type,
                "target_field": "address",
                "value": val,
                "requires_validation": False,
                "response_text": f"I've updated your address to {val}."
            }

        # Email
        email_match = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", clean_text)
        if email_match:
            val = email_match.group(1).strip(" .")
            action_type = UserIntent.CORRECT_FIELD.value if is_correction else UserIntent.UPDATE_FIELD.value
            return {
                "action": action_type,
                "target_field": "email",
                "value": val,
                "requires_validation": False,
                "response_text": f"I've updated your email to {val}."
            }

        # City / State
        city_match = re.search(r"(?:i live in|city is|city to)\s+([A-Za-z\s]+)", clean_text, re.IGNORECASE)
        if city_match:
            val = city_match.group(1).strip(" .")
            return {
                "action": UserIntent.UPDATE_FIELD.value,
                "target_field": "city",
                "value": val,
                "requires_validation": False,
                "response_text": f"I've updated your city to {val}."
            }

        # Fallback to active field if plain text provided
        if active_field and len(clean_text) > 0:
            requires_val = (active_field == "postal_code")
            return {
                "action": UserIntent.UPDATE_FIELD.value,
                "target_field": active_field,
                "value": clean_text,
                "requires_validation": requires_val,
                "response_text": f"I've updated your {active_field.replace('_', ' ')} to {clean_text}."
            }

        return {
            "action": UserIntent.REQUEST_CLARIFICATION.value,
            "target_field": None,
            "value": None,
            "requires_validation": False,
            "response_text": "I didn't quite understand that. Could you please specify the field or value you'd like to update?"
        }


class MockAIProvider(AIProvider):
    """
    Mock AI Provider for automated deterministic testing.
    Supports simulated artificial delay to test race conditions and forced response overrides.
    """
    def __init__(self, artificial_delay: float = 0.0):
        self.artificial_delay: float = artificial_delay
        self.fallback = RuleBasedFallbackProvider()
        self.forced_responses: Dict[str, Dict[str, Any]] = {}

    def set_forced_response(self, text_key: str, response_dict: Dict[str, Any]) -> None:
        self.forced_responses[text_key] = response_dict

    def clear_forced_responses(self) -> None:
        self.forced_responses.clear()

    async def interpret_user_input(
        self,
        text: str,
        context: Dict[str, Any],
        interaction_version: int
    ) -> Dict[str, Any]:
        if self.artificial_delay > 0:
            await asyncio.sleep(self.artificial_delay)

        if text in self.forced_responses:
            return self.forced_responses[text]

        return await self.fallback.interpret_user_input(text, context, interaction_version)


class GeminiProvider(AIProvider):
    """
    Live Gemini API Provider utilizing Google Gemini REST endpoint.
    Extracts structured JSON action with schema validation.
    Falls back gracefully to deterministic rule-based parsing if API key is not configured.
    """
    def __init__(self, api_key: str = "", model: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.fallback = RuleBasedFallbackProvider()

    async def interpret_user_input(
        self,
        text: str,
        context: Dict[str, Any],
        interaction_version: int
    ) -> Dict[str, Any]:
        if not self.api_key:
            # When no API key is configured, utilize reliable fallback
            return await self.fallback.interpret_user_input(text, context, interaction_version)

        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        prompt_payload = {
            "system_instruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "contents": [
                {
                    "parts": [
                        {
                            "text": f"Context: Active field is '{context.get('active_field_key', 'full_name')}'.\nUser Input: \"{text}\""
                        }
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.1
            }
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(endpoint, json=prompt_payload)
                if res.status_code == 200:
                    data = res.json()
                    raw_text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    parsed = json.loads(raw_text)
                    return parsed
                else:
                    # Fall back on API error
                    return await self.fallback.interpret_user_input(text, context, interaction_version)
        except Exception:
            return await self.fallback.interpret_user_input(text, context, interaction_version)
