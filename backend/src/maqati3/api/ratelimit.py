"""Rate limit for wrong upload keys, per client.

The key in the unlisted link is the only credential on the upload API, so guessing it has
to be slow. Only *wrong* keys count: a request without a key is not a guess, and the right
key is never penalised. A blocked client is refused before the key is looked at, even if
it would have been right; otherwise the block would only slow a guesser down.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import Request

DEFAULT_MAX_FAILURES = 30
DEFAULT_WINDOW_S = 600.0
DEFAULT_MAX_TRACKED = 10_000


class FailureLimiter:
    """Counts wrong keys per client inside a sliding window.

    Memory is bounded: expired clients are dropped on every failure, and past
    ``max_tracked`` the client with the fewest failures goes first. A flood of one-off
    addresses therefore pushes out other one-offs, never a client that is blocked.
    """

    def __init__(
        self,
        *,
        max_failures: int = DEFAULT_MAX_FAILURES,
        window_s: float = DEFAULT_WINDOW_S,
        max_tracked: int = DEFAULT_MAX_TRACKED,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_failures = max_failures
        self.window_s = window_s
        self._max_tracked = max_tracked
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()  # sync routes run in a thread pool

    def blocked(self, client: str) -> bool:
        with self._lock:
            recent = self._failures.get(client)
            if recent is None:
                return False
            self._expire(recent)
            if not recent:
                del self._failures[client]
                return False
            return len(recent) >= self.max_failures

    def record_failure(self, client: str) -> None:
        with self._lock:
            now = self._clock()
            self._drop_expired(now)
            recent = self._failures.setdefault(client, deque(maxlen=self.max_failures))
            recent.append(now)
            while len(self._failures) > self._max_tracked:
                weakest = min(self._failures, key=lambda c: (len(self._failures[c]), c))
                del self._failures[weakest]

    def tracked(self) -> int:
        with self._lock:
            return len(self._failures)

    def _expire(self, recent: deque[float]) -> None:
        horizon = self._clock() - self.window_s
        while recent and recent[0] <= horizon:
            recent.popleft()

    def _drop_expired(self, now: float) -> None:
        horizon = now - self.window_s
        for client in [c for c, hits in self._failures.items() if hits[-1] <= horizon]:
            del self._failures[client]


def client_address(request: Request, *, trust_forwarded_for: bool) -> str:
    """Who is asking. Behind our own proxy that is the last ``X-Forwarded-For`` entry:
    the proxy appends the address it saw, and anything a client put before it is theirs.
    Without a trusted proxy the header is ignored, because anyone can send it."""
    if trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for", "")
        last = forwarded.rsplit(",", 1)[-1].strip()
        if last:
            return last
    return request.client.host if request.client else "unknown"
