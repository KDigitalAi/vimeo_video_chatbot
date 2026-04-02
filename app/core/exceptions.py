"""Application-specific exception hierarchy."""
from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application error with HTTP metadata."""

    status_code = 500
    error_code = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(AppError):
    """Raised when request or domain validation fails."""

    status_code = 422
    error_code = "validation_error"


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    status_code = 404
    error_code = "not_found"


class DependencyError(AppError):
    """Raised when an external dependency is unavailable."""

    status_code = 503
    error_code = "dependency_unavailable"


class PersistenceError(AppError):
    """Raised when persistence work fails unexpectedly."""

    status_code = 503
    error_code = "persistence_error"
