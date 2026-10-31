"""Wrong upload keys are rate-limited per client.

The key is the only credential on the upload API, so guessing it must be slow. The
blocked cases come first: the limit exists for them.
"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient
from httpx import Response

from maqati3.api.app import create_app
from maqati3.api.ratelimit import FailureLimiter

KEY = "right-key"
LIMIT = 3
WINDOW_S = 60.0


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class Nothing:
    """The routes under test never reach the repository."""


def build(
    *, clock: Clock | None = None, max_tracked: int = 100, trust_forwarded_for: bool = False
) -> tuple[TestClient, FailureLimiter]:
    limiter = FailureLimiter(
        max_failures=LIMIT,
        window_s=WINDOW_S,
        max_tracked=max_tracked,
        clock=clock or Clock(),
    )
    app = create_app(
        Nothing(),  # type: ignore[arg-type]
        upload_key=KEY,
        key_limiter=limiter,
        trust_forwarded_for=trust_forwarded_for,
    )
    return TestClient(app), limiter


def post(client: TestClient, key: str | None, **headers: str) -> Response:
    if key is not None:
        headers["X-Upload-Key"] = key
    files = {"file": ("clip.mp4", io.BytesIO(b"x"), "video/mp4")}
    return client.post("/api/v1/uploads", files=files, headers=headers)


def fail_up_to_the_limit(client: TestClient, **headers: str) -> None:
    for _ in range(LIMIT):
        assert post(client, "wrong", **headers).status_code == 401


def test_after_too_many_wrong_keys_the_client_is_refused() -> None:
    client, _ = build()
    fail_up_to_the_limit(client)
    assert post(client, "wrong").status_code == 429


def test_a_blocked_client_is_refused_even_with_the_right_key() -> None:
    # Otherwise the guesser only has to keep going: the right guess would still get in.
    client, _ = build()
    fail_up_to_the_limit(client)
    assert post(client, KEY).status_code == 429


def test_the_media_route_counts_and_blocks_the_same_way() -> None:
    client, _ = build()
    for _ in range(LIMIT):
        assert client.get("/api/v1/uploads/abc/media?k=wrong").status_code == 401
    assert client.get("/api/v1/uploads/abc/media?k=wrong").status_code == 429
    assert post(client, KEY).status_code == 429


def test_the_block_ends_when_the_window_has_passed() -> None:
    clock = Clock()
    client, _ = build(clock=clock)
    fail_up_to_the_limit(client)
    clock.now += WINDOW_S + 1
    assert post(client, "wrong").status_code == 401


def test_a_request_without_any_key_is_not_a_guess() -> None:
    # A page opened without #k= has nothing to guess with; it must not lock itself out.
    client, _ = build()
    for _ in range(LIMIT + 2):
        assert post(client, None).status_code == 401
    assert post(client, "wrong").status_code == 401


def test_the_right_key_never_counts_against_the_client() -> None:
    client, _ = build()
    for _ in range(LIMIT + 2):
        assert post(client, KEY).status_code != 429


def test_a_forwarded_address_is_ignored_unless_the_proxy_is_trusted() -> None:
    # Anyone can send the header; honouring it everywhere would let a guesser rotate it.
    client, _ = build(trust_forwarded_for=False)
    for n in range(LIMIT):
        assert post(client, "wrong", **{"X-Forwarded-For": f"10.0.0.{n}"}).status_code == 401
    assert post(client, "wrong", **{"X-Forwarded-For": "10.0.0.99"}).status_code == 429


def test_behind_a_trusted_proxy_each_forwarded_address_is_counted_separately() -> None:
    client, _ = build(trust_forwarded_for=True)
    fail_up_to_the_limit(client, **{"X-Forwarded-For": "203.0.113.5"})
    assert post(client, "wrong", **{"X-Forwarded-For": "203.0.113.5"}).status_code == 429
    assert post(client, "wrong", **{"X-Forwarded-For": "203.0.113.6"}).status_code == 401


def test_the_rightmost_forwarded_address_is_the_one_the_proxy_saw() -> None:
    # A client can prepend anything; only the last entry was added by our own proxy.
    client, _ = build(trust_forwarded_for=True)
    for n in range(LIMIT):
        headers = {"X-Forwarded-For": f"10.9.9.{n}, 203.0.113.5"}
        assert post(client, "wrong", **headers).status_code == 401
    assert post(client, "wrong", **{"X-Forwarded-For": "10.1.1.1, 203.0.113.5"}).status_code == 429


def test_the_number_of_tracked_clients_is_capped() -> None:
    _, limiter = build(max_tracked=5)
    for n in range(50):
        limiter.record_failure(f"198.51.100.{n}")
    assert limiter.tracked() <= 5


def test_expired_failures_are_forgotten() -> None:
    clock = Clock()
    limiter = FailureLimiter(max_failures=LIMIT, window_s=WINDOW_S, max_tracked=100, clock=clock)
    limiter.record_failure("198.51.100.1")
    clock.now += WINDOW_S + 1
    limiter.record_failure("198.51.100.2")
    assert limiter.tracked() == 1


def test_flooding_the_limiter_with_other_clients_does_not_free_a_blocked_one() -> None:
    # The cap evicts the client with the fewest failures first, so a flood of one-off
    # addresses pushes out other one-offs, never the client that is blocked.
    limiter = FailureLimiter(max_failures=LIMIT, window_s=WINDOW_S, max_tracked=5, clock=Clock())
    for _ in range(LIMIT):
        limiter.record_failure("198.51.100.1")
    for n in range(50):
        limiter.record_failure(f"203.0.113.{n}")
    assert limiter.blocked("198.51.100.1") is True
