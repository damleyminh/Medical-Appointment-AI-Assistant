"""
ContextEditingMiddleware — modifies the conversation context before it
is sent to the LLM.

Responsibilities:
  • Inject system instructions
  • Trim message history to stay within token limits
  • Remove or redact sensitive content from context
  • Append relevant background data (e.g. patient record snippets)
"""
from __future__ import annotations
import logging
from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

logger = logging.getLogger(__name__)

# Rough token estimate: 1 token ≈ 4 characters
_CHARS_PER_TOKEN = 4


def _estimate_tokens(messages: list) -> int:
    total = 0
    for m in messages:
        content = m.content if hasattr(m, "content") else str(m)
        total += len(content) // _CHARS_PER_TOKEN
    return total


class ContextEditingMiddleware:
    """
    Edits the message context before LLM invocation.

    Features:
      - trim_to_token_limit : drops oldest messages when context is too long
      - inject_system       : ensures a system message is always present
      - append_context      : appends extra background info to the last user message
      - redact_keywords     : removes specified sensitive keywords from context

    Usage:
        ctx = ContextEditingMiddleware(
            max_tokens=3000,
            system_prompt="You are a medical appointment coordinator.",
        )
        messages = ctx.edit(messages, extra_context="Patient has MRI booked for March 5.")
        response = llm.invoke(messages)
    """

    def __init__(
        self,
        max_tokens: int = 3000,
        system_prompt: str | None = None,
        redact_keywords: list[str] | None = None,
    ):
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt
        self.redact_keywords = [kw.lower() for kw in (redact_keywords or [])]

    def edit(self, messages: list, extra_context: str | None = None) -> list:
        """
        Apply all editing steps and return the modified message list.
        """
        messages = list(messages)  # don't mutate original

        # 1. Inject / update system prompt
        if self.system_prompt:
            messages = self._inject_system(messages)

        # 2. Append extra context to last user message
        if extra_context:
            messages = self._append_context(messages, extra_context)

        # 3. Redact sensitive keywords
        if self.redact_keywords:
            messages = self._redact(messages)

        # 4. Trim to token limit (drop oldest non-system messages)
        messages = self._trim(messages)

        logger.debug(
            "ContextEditingMiddleware: %d messages, ~%d tokens after editing",
            len(messages), _estimate_tokens(messages)
        )
        return messages

    def _inject_system(self, messages: list) -> list:
        if messages and isinstance(messages[0], SystemMessage):
            messages[0] = SystemMessage(content=self.system_prompt)
        else:
            messages.insert(0, SystemMessage(content=self.system_prompt))
        return messages

    def _append_context(self, messages: list, extra: str) -> list:
        for i in reversed(range(len(messages))):
            if isinstance(messages[i], HumanMessage):
                messages[i] = HumanMessage(
                    content=f"{messages[i].content}\n\n[Context: {extra}]"
                )
                break
        return messages

    def _redact(self, messages: list) -> list:
        result = []
        for m in messages:
            content = m.content if hasattr(m, "content") else str(m)
            for kw in self.redact_keywords:
                content = content.replace(kw, "[REDACTED]")
            if isinstance(m, SystemMessage):
                result.append(SystemMessage(content=content))
            elif isinstance(m, HumanMessage):
                result.append(HumanMessage(content=content))
            elif isinstance(m, AIMessage):
                result.append(AIMessage(content=content))
            else:
                result.append(m)
        return result

    def _trim(self, messages: list) -> list:
        if _estimate_tokens(messages) <= self.max_tokens:
            return messages
        # Keep system message at index 0, trim from oldest human/ai messages
        system = [m for m in messages if isinstance(m, SystemMessage)]
        rest   = [m for m in messages if not isinstance(m, SystemMessage)]
        while rest and _estimate_tokens(system + rest) > self.max_tokens:
            rest.pop(0)
        logger.info("ContextEditingMiddleware: trimmed context to %d messages", len(system + rest))
        return system + rest
