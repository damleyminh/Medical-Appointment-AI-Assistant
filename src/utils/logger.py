"""
Run logger — structured trace output with PII masking.
Logs are printed to stdout and optionally written to runs/<run_id>.json.
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any


_MASK_PATTERNS = [
    (re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "[EMAIL]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    (re.compile(r"\b(?:sk-|pk-)[A-Za-z0-9\-_]{20,}\b"), "[API_KEY]"),
]


def _mask(text: str) -> str:
    for pattern, replacement in _MASK_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RunLogger:
    def __init__(self, persist: bool = True):
        self.persist = persist
        self._events: list[dict] = []
        self.run_id: str | None = None
        self.log_path: Path | None = None

    def start(self, run_id: str) -> None:
        self.run_id = run_id
        self._events = []
        if self.persist:
            log_dir = Path("runs")
            log_dir.mkdir(exist_ok=True)
            self.log_path = log_dir / f"{run_id}.json"

    def log(self, node: str, event: str, detail: Any = None) -> None:
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "node": node,
            "event": event,
            "detail": _mask(str(detail)) if detail is not None else None,
        }
        self._events.append(entry)
        if os.getenv("LANGGRAPH_TRACE", "false").lower() == "true":
            print(f"  [{entry['ts']}] [{node}] {event}" +
                  (f" — {entry['detail']}" if entry["detail"] else ""))

    def flush(self) -> list[dict]:
        if self.persist and self.log_path:
            self.log_path.write_text(json.dumps(self._events, indent=2))
        return self._events

    def summary(self, state: dict) -> dict:
        return {
            "run_id": state.get("run_id"),
            "timestamp": state.get("timestamp"),
            "status": state.get("status"),
            "intent": state.get("intent"),
            "route_path": state.get("route_path", []),
            "hitl_action": state.get("hitl_action"),
            "moderation_flagged": state.get("moderation_flagged"),
            "call_count": state.get("call_count"),
            "pii_detected": bool(state.get("pii_map")),
        }
