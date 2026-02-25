"""
ModelFallbackMiddleware — automatically switches to a backup LLM
if the primary model fails or is unavailable.

Supports a chain of fallback models tried in order.
"""
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ModelFallbackMiddleware:
    """
    Tries each LLM in the provided chain in order.
    Returns the first successful response.

    Usage:
        from langchain_openai import ChatOpenAI
        primary  = ChatOpenAI(model="gpt-4o")
        fallback = ChatOpenAI(model="gpt-3.5-turbo")
        mfm = ModelFallbackMiddleware(models=[primary, fallback])
        response = mfm.invoke(messages)
    """

    def __init__(self, models: list):
        if not models:
            raise ValueError("ModelFallbackMiddleware requires at least one model.")
        self.models = models

    def invoke(self, messages: list) -> Any:
        """
        Try each model in order. Returns first successful response.
        Raises RuntimeError if all models fail.
        """
        errors = []
        for i, model in enumerate(self.models):
            try:
                response = model.invoke(messages)
                if i > 0:
                    logger.info(
                        "ModelFallbackMiddleware: primary failed, used fallback model #%d", i
                    )
                return response
            except Exception as exc:
                errors.append(f"Model {i} ({getattr(model, 'model_name', '?')}): {exc}")
                logger.warning(
                    "ModelFallbackMiddleware: model #%d failed: %s", i, exc
                )
        raise RuntimeError(
            f"ModelFallbackMiddleware: all {len(self.models)} models failed.\n"
            + "\n".join(errors)
        )
