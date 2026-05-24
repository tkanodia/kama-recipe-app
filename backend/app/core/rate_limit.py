"""Rate limiting configuration using SlowAPI with Redis backend."""

from fastapi import Request
from slowapi import Limiter

from app.core.config import get_settings

_settings = get_settings()


def _rate_limit_key(request: Request) -> str:
    """Extract user ID from Clerk JWT for rate-limit keying; fall back to IP."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer ") and not _settings.disable_auth:
        try:
            from app.core.auth import verify_bearer_token
            return verify_bearer_token(auth.split(" ", 1)[1].strip())
        except Exception:
            pass
    return request.client.host if request.client else "unknown"


limiter = Limiter(
    key_func=_rate_limit_key,
    storage_uri=_settings.redis_url,
    default_limits=[],
)
