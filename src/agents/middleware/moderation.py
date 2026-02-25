"""
ModerationMiddleware — calls the OpenAI Moderation API to screen patient
input before it is processed. Flagged messages are routed to ESCALATE.
Falls back gracefully if the API call fails (non-blocking).
"""
import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)


class ModerationMiddleware:
    """
    Wraps OpenAI's moderation endpoint. Returns a simple (flagged, categories)
    tuple so the graph node can decide on routing.
    """

    def __init__(self):
        self._client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return self._client

    def check(self, text: str) -> tuple[bool, list[str]]:
        """
        Returns (flagged: bool, triggered_categories: list[str]).
        On API error, returns (False, []) to avoid blocking the workflow.
        """
        try:
            response = self._get_client().moderations.create(input=text)
            result = response.results[0]
            if result.flagged:
                triggered = [
                    cat for cat, val in result.categories.model_dump().items() if val
                ]
                return True, triggered
            return False, []
        except Exception as exc:
            logger.warning("Moderation API call failed (non-blocking): %s", exc)
            return False, []
