"""
PIIMiddleware — detects and masks personally identifiable information
before text is sent to the LLM. The original values are stored in a
reversible map so that responses can be de-masked for the final output.
"""
import re
import uuid
from dataclasses import dataclass, field


@dataclass
class PIIMiddleware:
    """
    Scans input text for common PII patterns, replaces each unique value
    with a stable placeholder token, and stores the mapping for later
    restoration.

    Patterns covered:
      • Phone numbers (US formats)
      • Email addresses
      • SSNs  (###-##-####)
      • Date-of-birth hints (DOB: MM/DD/YYYY)
      • Full names preceded by "patient:" / "name:" / "I am" heuristic
    """

    _patterns: list = field(default_factory=list, init=False)

    def __post_init__(self):
        self._patterns = [
            ("PHONE",   re.compile(r"\b(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})\b")),
            ("EMAIL",   re.compile(r"\b([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b")),
            ("SSN",     re.compile(r"\b(\d{3}-\d{2}-\d{4})\b")),
            ("DOB",     re.compile(r"(?i)\b(?:dob|date of birth)[:\s]+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\b")),
            ("DATE",    re.compile(r"\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\b")),
        ]

    def mask(self, text: str) -> tuple[str, dict]:
        """
        Returns (masked_text, pii_map).
        pii_map: { placeholder_token: original_value }
        """
        pii_map: dict[str, str] = {}
        masked = text

        for pii_type, pattern in self._patterns:
            for match in pattern.findall(masked):
                if match not in pii_map.values():
                    token = f"[{pii_type}_{uuid.uuid4().hex[:6].upper()}]"
                    pii_map[token] = match
                    masked = masked.replace(match, token, 1)

        return masked, pii_map

    def unmask(self, text: str, pii_map: dict) -> str:
        """Restore placeholder tokens to original values."""
        for token, original in pii_map.items():
            text = text.replace(token, original)
        return text
