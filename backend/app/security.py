"""Small, dependency-free hardening helpers shared by the API.

- `is_production()`: true on Render (it sets RENDER) or when ENV / APP_ENV is "production".
- `RateLimiter`: in-memory sliding-window limiter (per process; Render runs one).
- `BodySizeLimitMiddleware`: rejects request bodies over a byte limit with 413.
- `SecurityHeadersMiddleware`: conservative headers on every API response.
- `client_ip()`: the caller's address, using the proxy's own X-Forwarded-For hop on Render.

Findings and reasoning: docs/security-review.md.
"""

import os
import threading
import time
from collections import deque

from fastapi import HTTPException, Request, status
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# ---- environment -----------------------------------------------------------------------


def is_production() -> bool:
    if os.getenv("RENDER"):
        return True
    for name in ("ENV", "APP_ENV", "ENVIRONMENT"):
        if (os.getenv(name) or "").strip().lower() in ("production", "prod"):
            return True
    return False


# ---- rate limiting ---------------------------------------------------------------------


class RateLimiter:
    """At most `limit` hits per `window` seconds for each key.

    In memory, so limits reset when the process restarts and are not shared between
    processes. That is enough to stop a single client from hammering an expensive
    route (language model, phone calls, scrypt); it is not a substitute for an edge
    rate limiter.
    """

    _all: "list[RateLimiter]" = []

    def __init__(self, name: str, limit: int, window: float):
        self.name = name
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        RateLimiter._all.append(self)

    def _prune(self, key: str, now: float) -> deque[float]:
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        return hits

    def hit(self, key: str) -> int:
        """Counts one hit. Returns 0 when allowed, otherwise seconds until the next slot."""
        with self._lock:
            now = time.monotonic()
            hits = self._prune(key, now)
            if len(hits) >= self.limit:
                return max(1, int(self.window - (now - hits[0]) + 0.999))
            hits.append(now)
            if len(self._hits) > 10_000:  # keep memory bounded under key spraying
                for stale in [k for k, v in self._hits.items() if not v][:5_000]:
                    self._hits.pop(stale, None)
            return 0

    def blocked(self, key: str) -> int:
        """Like hit() but without counting. Returns seconds to wait, or 0."""
        with self._lock:
            now = time.monotonic()
            hits = self._prune(key, now)
            if len(hits) >= self.limit:
                return max(1, int(self.window - (now - hits[0]) + 0.999))
            return 0

    def clear(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)

    @classmethod
    def reset_all(cls) -> None:
        """Tests only."""
        for limiter in cls._all:
            limiter.clear()


def too_many(detail: str, wait: int) -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        f"{detail} Please wait {wait} seconds.",
        headers={"Retry-After": str(wait)},
    )


def client_ip(request: Request) -> str:
    """Best-effort caller address.

    Behind Render's proxy the socket peer is the proxy, so the last X-Forwarded-For hop
    (the one Render appends, which the caller cannot forge) is used there. Elsewhere the
    header is ignored because anyone can send it.
    """
    if is_production():
        forwarded = request.headers.get("x-forwarded-for", "")
        hops = [h.strip() for h in forwarded.split(",") if h.strip()]
        if hops:
            return hops[-1]
    return request.client.host if request.client else "unknown"


# ---- request body size -----------------------------------------------------------------

MAX_BODY_BYTES = 256 * 1024


class BodySizeLimitMiddleware:
    """413 for bodies larger than `max_bytes`, by Content-Length or while streaming."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        for name, value in scope.get("headers") or []:
            if name == b"content-length":
                try:
                    too_big = int(value) > self.max_bytes
                except ValueError:
                    too_big = True
                if too_big:
                    await _reject_413(send)
                    return

        received = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLarge()
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if not response_started:
                await _reject_413(send)


class _BodyTooLarge(HTTPException):
    """An HTTPException so FastAPI's body parsing re-raises it as a 413 instead of a 400."""

    def __init__(self):
        super().__init__(status.HTTP_413_CONTENT_TOO_LARGE, "Request body is too large")


async def _reject_413(send: Send) -> None:
    body = b'{"detail":"Request body is too large"}'
    await send({
        "type": "http.response.start",
        "status": 413,
        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
    })
    await send({"type": "http.response.body", "body": body})


# ---- response headers ------------------------------------------------------------------

API_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-site",
}


class SecurityHeadersMiddleware:
    """Adds API_SECURITY_HEADERS, plus Cache-Control: no-store on authenticated requests
    so patient data is never kept by a shared cache. HSTS is added in production."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        authed = any(name == b"authorization" for name, _ in scope.get("headers") or [])
        production = is_production()

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                present = {name.lower() for name, _ in headers}
                extra = dict(API_SECURITY_HEADERS)
                if production:
                    extra["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
                if authed:
                    extra["Cache-Control"] = "no-store"
                for key, value in extra.items():
                    if key.lower().encode() not in present:
                        headers.append((key.lower().encode(), value.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)
