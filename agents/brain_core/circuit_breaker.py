"""A minimal async circuit breaker for protecting flaky downstream calls.

After N consecutive failures the breaker opens and fast-fails calls for a cooldown
window instead of hammering a broken dependency (e.g. a stalled local model). After
the cooldown it half-opens and lets one trial call decide whether to close again.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class CircuitOpenError(RuntimeError):
    """Raised when a call is rejected because the circuit is open."""


class CircuitBreaker:
    """Simple consecutive-failure circuit breaker."""

    def __init__(self, name: str, threshold: int = 5, cooldown: float = 30.0) -> None:
        """Initialize the breaker.

        Args:
            name: Identifier for logs/metrics.
            threshold: Consecutive failures before opening.
            cooldown: Seconds to stay open before a trial call.
        """
        self.name = name
        self.threshold = threshold
        self.cooldown = cooldown
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        """Whether the circuit is currently open (still within cooldown)."""
        if self._opened_at is None:
            return False
        return (time.monotonic() - self._opened_at) < self.cooldown

    async def call(self, fn: Callable[[], Awaitable[T]]) -> T:
        """Run ``fn`` through the breaker, fast-failing if open."""
        if self.is_open:
            raise CircuitOpenError(f"circuit '{self.name}' is open")
        try:
            result = await fn()
        except Exception:
            self._failures += 1
            if self._failures >= self.threshold:
                self._opened_at = time.monotonic()
            raise
        # Success closes the breaker.
        self._failures = 0
        self._opened_at = None
        return result
