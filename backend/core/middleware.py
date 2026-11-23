"""Response hardening headers for every API response."""

from starlette.middleware.base import BaseHTTPMiddleware

from config import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        # Responses carry personal data and tokens: never let a cache keep them.
        headers.setdefault("Cache-Control", "no-store")
        if get_settings().is_production:
            headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        return response
