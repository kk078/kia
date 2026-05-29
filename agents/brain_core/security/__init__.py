"""Security utilities: runtime guard against prompt injection in untrusted content."""

from brain_core.security.guard import (
    Finding,
    SanitizationResult,
    Severity,
    sanitize_untrusted,
    wrap_untrusted,
)

__all__ = [
    "Finding",
    "SanitizationResult",
    "Severity",
    "sanitize_untrusted",
    "wrap_untrusted",
]
