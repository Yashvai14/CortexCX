"""Real progress events from the AI pipeline (used by the streaming chat endpoint).

The orchestrator calls `emit("searching")` / `emit("writing")` at the real stage boundaries. When a streaming
request has installed a callback (via `set_progress`) the customer's chat shows those stages as they happen;
otherwise `emit` does nothing.
"""
from contextvars import ContextVar, Token
from typing import Callable

_callback: ContextVar[Callable[[str], None] | None] = ContextVar("pipeline_progress", default=None)


def set_progress(cb: Callable[[str], None] | None) -> Token:
    return _callback.set(cb)


def reset_progress(token: Token) -> None:
    _callback.reset(token)


def emit(stage: str) -> None:
    cb = _callback.get()
    if cb is not None:
        try:
            cb(stage)
        except Exception:
            pass  # progress reporting must never break answering
