import asyncio
from typing import Dict, Any, Optional

# Mock Postal Code Database with realistic geographical grounding
POSTAL_CODE_DB: Dict[str, Dict[str, str]] = {
    "600001": {"city": "Chennai", "state": "Tamil Nadu", "region": "George Town"},
    "600028": {"city": "Chennai", "state": "Tamil Nadu", "region": "R.A. Puram / Mylapore"},
    "10001": {"city": "New York", "state": "NY", "region": "Manhattan"},
    "94103": {"city": "San Francisco", "state": "CA", "region": "SoMa"},
    "90210": {"city": "Beverly Hills", "state": "CA", "region": "Beverly Hills"},
    "560001": {"city": "Bangalore", "state": "Karnataka", "region": "MG Road / Central"},
    "110001": {"city": "New Delhi", "state": "Delhi", "region": "Connaught Place"},
}

class ValidationService:
    """
    Simulates asynchronous, potentially long-running external API validation
    (e.g., postal code lookup, address verification, credit check).
    Supports configurable artificial delays to allow deterministic stress testing.
    """
    def __init__(self, default_delay: float = 0.0):
        self.artificial_delay: float = default_delay

    def set_artificial_delay(self, delay_seconds: float) -> None:
        self.artificial_delay = max(0.0, delay_seconds)

    async def validate_postal_code(
        self,
        postal_code: str,
        custom_delay: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Validates postal code with async delay.
        Supports cancellation via standard asyncio Cancellation token.
        """
        delay = custom_delay if custom_delay is not None else self.artificial_delay
        if delay > 0:
            await asyncio.sleep(delay)

        clean_code = postal_code.strip()
        if clean_code in POSTAL_CODE_DB:
            details = POSTAL_CODE_DB[clean_code]
            return {
                "is_valid": True,
                "postal_code": clean_code,
                "city": details["city"],
                "state": details["state"],
                "region": details["region"],
                "message": f"Verified: {details['city']}, {details['state']}"
            }
        else:
            # Check basic 5 or 6 digit format
            if clean_code.isdigit() and len(clean_code) in (5, 6):
                return {
                    "is_valid": True,
                    "postal_code": clean_code,
                    "city": "Unknown City",
                    "state": "Unknown State",
                    "message": "Valid postal code format"
                }
            return {
                "is_valid": False,
                "postal_code": clean_code,
                "message": f"Invalid postal code '{clean_code}'"
            }
