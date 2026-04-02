"""Request-scoped observability context."""
from __future__ import annotations

from contextvars import ContextVar, Token

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
_session_id_var: ContextVar[str | None] = ContextVar("session_id", default=None)
_path_var: ContextVar[str | None] = ContextVar("path", default=None)
_method_var: ContextVar[str | None] = ContextVar("method", default=None)


def set_request_context(
    *,
    request_id: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    path: str | None = None,
    method: str | None = None,
) -> dict[str, Token]:
    """Set request-scoped context variables and return reset tokens."""
    return {
        "request_id": _request_id_var.set(request_id),
        "user_id": _user_id_var.set(user_id),
        "session_id": _session_id_var.set(session_id),
        "path": _path_var.set(path),
        "method": _method_var.set(method),
    }


def get_request_context() -> dict[str, str | None]:
    """Return the current request-scoped context."""
    return {
        "request_id": _request_id_var.get(),
        "user_id": _user_id_var.get(),
        "session_id": _session_id_var.get(),
        "path": _path_var.get(),
        "method": _method_var.get(),
    }


def enrich_request_context(*, user_id: str | None = None, session_id: str | None = None) -> None:
    """Update request context when user/session identity becomes known later."""
    if user_id is not None:
        _user_id_var.set(user_id)
    if session_id is not None:
        _session_id_var.set(session_id)


def reset_request_context(tokens: dict[str, Token]) -> None:
    """Reset request-scoped context variables using saved tokens."""
    _request_id_var.reset(tokens["request_id"])
    _user_id_var.reset(tokens["user_id"])
    _session_id_var.reset(tokens["session_id"])
    _path_var.reset(tokens["path"])
    _method_var.reset(tokens["method"])
