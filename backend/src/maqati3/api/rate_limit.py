"""Rate limiting for sensitive endpoints against credential guessing."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class UploadKeyRateLimiter:
    """Sliding-window in-memory rate limiter for failed upload key attempts.

    Blocks client IP addresses after ``max_failures`` within ``window_s`` for
    ``block_s``.
    """

    max_failures: int = 5
    window_s: float = 60.0
    block_s: float = 300.0
    _failures: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    _blocked_until: dict[str, float] = field(default_factory=dict)

    def is_blocked(self, client_ip: str, now: float | None = None) -> bool:
        t = time.monotonic() if now is None else now
        blocked_until = self._blocked_until.get(client_ip)
        if blocked_until is not None:
            if t < blocked_until:
                return True
            del self._blocked_until[client_ip]
        return False

    def record_failure(self, client_ip: str, now: float | None = None) -> bool:
        """Record a failed attempt. Returns True if client is now blocked."""
        t = time.monotonic() if now is None else now
        if self.is_blocked(client_ip, now=t):
            return True

        window_start = t - self.window_s
        attempts = [ts for ts in self._failures[client_ip] if ts > window_start]
        attempts.append(t)
        self._failures[client_ip] = attempts

        if len(attempts) >= self.max_failures:
            self._blocked_until[client_ip] = t + self.block_s
            self._failures.pop(client_ip, None)
            return True
        return False

    def record_success(self, client_ip: str) -> None:
        """Clear failure count on successful key authentication."""
        self._failures.pop(client_ip, None)

    def reset(self) -> None:
        """Reset all rate limiter state."""
        self._failures.clear()
        self._blocked_until.clear()
