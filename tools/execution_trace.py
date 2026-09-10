"""Execution trace and structured failure categories for LLM observability."""

import time
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional


class FailureCategory(str, Enum):
    """Structured LLM failure categories — never silently swallowed."""

    SUCCESS = "success"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    INVALID_JSON = "invalid_json"
    VALIDATION_ERROR = "validation_error"
    API_ERROR = "api_error"
    EMPTY_RESPONSE = "empty_response"
    UNKNOWN = "unknown"


@dataclass
class TraceEntry:
    """Single LLM call trace record."""

    stage: str
    method: str
    agent: str
    status: str  # "success" | failure category string
    duration_ms: float = 0.0
    error_message: Optional[str] = None
    failure_category: Optional[str] = None


class ExecutionTrace:
    """Module-level LLM call trace. Thread-safe append-only list."""

    def __init__(self) -> None:
        self._entries: List[TraceEntry] = []

    def record(
        self,
        stage: str,
        method: str,
        agent: str,
        status: str,
        duration_ms: float = 0.0,
        error_message: Optional[str] = None,
        failure_category: Optional[str] = None,
    ) -> TraceEntry:
        entry = TraceEntry(
            stage=stage,
            method=method,
            agent=agent,
            status=status,
            duration_ms=duration_ms,
            error_message=error_message,
            failure_category=failure_category,
        )
        self._entries.append(entry)
        return entry

    @property
    def entries(self) -> List[TraceEntry]:
        return list(self._entries)

    def summary(self) -> dict:
        total = len(self._entries)
        successes = sum(1 for e in self._entries if e.status == "success")
        failures = total - successes
        categories = {}
        for e in self._entries:
            cat = e.failure_category or e.status
            categories[cat] = categories.get(cat, 0) + 1
        total_duration = sum(e.duration_ms for e in self._entries)
        return {
            "total_calls": total,
            "successes": successes,
            "failures": failures,
            "failure_categories": categories,
            "total_duration_ms": round(total_duration, 1),
            "total_duration_s": round(total_duration / 1000, 2),
        }

    def clear(self) -> None:
        self._entries.clear()


def classify_exception(exc: Exception) -> str:
    """Map an exception to a structured FailureCategory string."""
    msg = str(exc).lower()
    if "429" in msg or "resource_exhausted" in msg or "rate" in msg:
        return FailureCategory.RATE_LIMITED
    if "504" in msg or "timeout" in msg or "deadline" in msg:
        return FailureCategory.TIMEOUT
    if "json" in msg or "decode" in msg or "parse" in msg:
        return FailureCategory.INVALID_JSON
    if "validation" in msg or "pydantic" in msg or "schema" in msg:
        return FailureCategory.VALIDATION_ERROR
    if "empty" in msg or "null" in msg or "no content" in msg:
        return FailureCategory.EMPTY_RESPONSE
    return FailureCategory.API_ERROR


# Module-level singleton — cleared per pipeline run
_trace = ExecutionTrace()


def get_trace() -> ExecutionTrace:
    return _trace


def reset_trace() -> None:
    _trace.clear()
