"""
RetryMiddleware — automatic retry logic for LLM model calls and tool calls.

ModelRetryMiddleware: retries LLM invocations on transient failures.
ToolRetryMiddleware:  retries tool function calls on transient failures.
"""
from __future__ import annotations
import time
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)


class ModelRetryMiddleware:
    """
    Wraps an LLM call with automatic retry logic.
    Retries on any exception with exponential backoff.

    Usage:
        retry = ModelRetryMiddleware(max_retries=3, backoff=1.5)
        response = retry.invoke(llm, messages)
    """

    def __init__(self, max_retries: int = 3, backoff: float = 1.5):
        self.max_retries = max_retries
        self.backoff = backoff

    def invoke(self, llm, messages: list) -> Any:
        """
        Invoke the LLM with retry. Raises the last exception if all retries fail.
        """
        last_exc = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return llm.invoke(messages)
            except Exception as exc:
                last_exc = exc
                wait = self.backoff ** (attempt - 1)
                logger.warning(
                    "ModelRetryMiddleware: attempt %d/%d failed (%s). "
                    "Retrying in %.1fs...", attempt, self.max_retries, exc, wait
                )
                if attempt < self.max_retries:
                    time.sleep(wait)
        raise RuntimeError(
            f"ModelRetryMiddleware: all {self.max_retries} attempts failed. "
            f"Last error: {last_exc}"
        )


class ToolRetryMiddleware:
    """
    Wraps a tool function call with automatic retry logic.
    Useful for flaky external APIs or data sources.

    Usage:
        retry = ToolRetryMiddleware(max_retries=3)
        result = retry.call(get_available_slots, "mri")
    """

    def __init__(self, max_retries: int = 3, backoff: float = 1.0):
        self.max_retries = max_retries
        self.backoff = backoff

    def call(self, fn: Callable, *args, **kwargs) -> Any:
        """
        Call a tool function with retry. Raises last exception if all retries fail.
        """
        last_exc = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                wait = self.backoff * attempt
                logger.warning(
                    "ToolRetryMiddleware: attempt %d/%d for '%s' failed (%s). "
                    "Retrying in %.1fs...", attempt, self.max_retries,
                    getattr(fn, "__name__", str(fn)), exc, wait
                )
                if attempt < self.max_retries:
                    time.sleep(wait)
        raise RuntimeError(
            f"ToolRetryMiddleware: all {self.max_retries} attempts failed for "
            f"'{getattr(fn, '__name__', str(fn))}'. Last error: {last_exc}"
        )
