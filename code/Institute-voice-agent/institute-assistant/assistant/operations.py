"""Carry deadlines, progress and safe provider measurements outside saved graph state."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from threading import Event, RLock
from time import monotonic


class OperationStopped(RuntimeError):
    """A stable cancellation/deadline category with no provider or student content."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass
class Operation:
    conversation_id: str
    turn_id: str
    deadline: float
    cancelled: Event = field(default_factory=Event)
    progress: object = None
    attempts: list = field(default_factory=list)
    lock: RLock = field(default_factory=RLock)

    def check(self):
        """Check before expensive calls and action commits, including after lock waits."""
        if self.cancelled.is_set():
            raise OperationStopped("cancelled")
        if monotonic() >= self.deadline:
            raise OperationStopped("deadline_exceeded")


_CURRENT = ContextVar("helpdesk_operation", default=None)
# The most recent provider measurement (numeric allowlist only), published on
# every call regardless of whether an Operation is active. This lets the metrics
# layer surface per-call token counts and durations (cost model 02 §2, §8) even
# in the benchmark harness, which runs the graph without an Operation context.
_LAST_MEASUREMENT = ContextVar("helpdesk_last_measurement", default=None)

# The numeric fields a provider response may contribute. Ollama reports durations
# in nanoseconds. Nothing outside this allowlist is ever retained.
_PROVIDER_NUMERIC_FIELDS = ("total_duration", "load_duration", "prompt_eval_count",
                            "prompt_eval_duration", "eval_count", "eval_duration")


@contextmanager
def operation_context(operation):
    """Propagate operation context through LangGraph without serializing callbacks/locks."""
    token = _CURRENT.set(operation)
    try:
        yield operation
    finally:
        _CURRENT.reset(token)


def current():
    """Expose optional context for CLI-compatible storage and inference adapters."""
    return _CURRENT.get()


def check(stage=None):
    """Publish a stage only after ensuring the submitted operation is still live."""
    operation = current()
    if operation:
        operation.check()
        if stage and operation.progress:
            operation.progress(stage)


def remaining(default):
    """Use the remaining turn budget rather than restarting a per-call deadline."""
    check()
    operation = current()
    return max(.001, min(default, operation.deadline - monotonic())) if operation else default


def last_measurement():
    """Return the numeric allowlist from the most recent provider call, or None.

    Safe to read anywhere: it holds only durations and token counts, never a
    prompt, question or provider body.
    """
    return _LAST_MEASUREMENT.get()


def clear_measurement():
    """Forget the last provider measurement before a call that may not report one."""
    _LAST_MEASUREMENT.set(None)


def record_attempt(provider, started, fields=None, error=None):
    """Retain a strict allowlist of numeric measurements, never raw provider responses."""
    row = {"provider": provider, "milliseconds": round((monotonic() - started) * 1000, 3)}
    for key in _PROVIDER_NUMERIC_FIELDS:
        value = (fields or {}).get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
            row[key] = value
    if error:
        row["error_code"] = type(error).__name__
    # Publish to the context-local slot on every call so the metrics layer can
    # read per-call token counts even without an Operation (e.g. the benchmark).
    _LAST_MEASUREMENT.set(row)
    operation = current()
    if operation:
        with operation.lock:
            operation.attempts.append(row)
