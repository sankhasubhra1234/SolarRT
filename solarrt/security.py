"""Security helpers: per-client rate limiting, request-size limits and browser security headers."""

from __future__ import annotations

import re
import time
from collections import OrderedDict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimiter:
    """Sliding-window limiter keyed by client (IP). Memory is bounded: at most `max_clients`
    clients are tracked, the least recently seen ones are forgotten first."""

    def __init__(self, limit: int, window_s: float, max_clients: int = 10_000) -> None:
        self.limit, self.window_s, self.max_clients = limit, window_s, max_clients
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()

    def allow(self, client: str) -> bool:
        now = time.monotonic()
        q = self._hits.get(client)
        if q is None:
            q = self._hits[client] = deque()
            while len(self._hits) > self.max_clients:
                self._hits.popitem(last=False)
        self._hits.move_to_end(client)
        while q and now - q[0] > self.window_s:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


def client_ip(request: Request) -> str:
    # Behind the HTTPS proxy, uvicorn's --proxy-headers already puts the real visitor IP
    # (from X-Forwarded-For, trusted only from the proxy) into request.client.
    return request.client.host if request.client else "unknown"


# Content Security Policy: only our own scripts run; map tiles and cloud images may come
# from the two tile services; the browser may call the IP-location services on first visit.
CSP = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https://server.arcgisonline.com https://view.eumetsat.int; connect-src 'self' https://get.geojs.io https://ipapi.co; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"

SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(self), camera=(), microphone=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


class SecurityMiddleware(BaseHTTPMiddleware):
    """Adds security headers, limits request bodies and rate-limits the API per client."""

    def __init__(self, app, api_limit: RateLimiter, search_limit: RateLimiter,
                 max_body: int = 64 * 1024) -> None:
        super().__init__(app)
        self.api_limit, self.search_limit, self.max_body = api_limit, search_limit, max_body

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                size = int(request.headers.get("content-length", "0"))
            except ValueError:
                size = self.max_body + 1
            if size < 0 or size > self.max_body:
                return self._finish(JSONResponse({"detail": "Request too large"}, status_code=413))

        if path.startswith("/api/") and path != "/api/health":
            ip = client_ip(request)
            if not self.api_limit.allow(ip):
                return self._finish(JSONResponse(
                    {"detail": "Too many requests — please slow down."}, status_code=429,
                    headers={"Retry-After": "60"}))
            # Place search uses OpenStreetMap's shared, rate-limited service: stricter limit.
            if path in ("/api/geocode", "/api/reverse") and not self.search_limit.allow(ip):
                return self._finish(JSONResponse(
                    {"detail": "Too many place searches — please wait a minute."}, status_code=429,
                    headers={"Retry-After": "60"}))

        if request.method in ("POST", "PUT", "PATCH"):
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > self.max_body:
                    return self._finish(JSONResponse({"detail": "Request too large"}, status_code=413))
                body.extend(chunk)
            # BaseHTTPMiddleware replays the cached body to the downstream parser.
            request._body = bytes(body)

        return self._finish(await call_next(request))

    @staticmethod
    def _finish(response: Response) -> Response:
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response


_LANG = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})?$")


def safe_language(header: str | None) -> str:
    """First language tag from Accept-Language if it is well-formed, else English."""
    first = (header or "").split(",")[0].split(";")[0].strip()
    return first if _LANG.match(first) else "en"
