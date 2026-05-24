from typing import Annotated

import jwt
import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.core.config import get_settings

log = structlog.get_logger()
security = HTTPBearer(auto_error=False)
_settings = get_settings()

_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        if not _settings.clerk_jwks_url:
            raise RuntimeError("CLERK_JWKS_URL is not configured")
        _jwks_client = PyJWKClient(
            _settings.clerk_jwks_url,
            cache_keys=True,
            max_cached_keys=16,
        )
    return _jwks_client


def verify_bearer_token(token: str) -> str:
    if _settings.disable_auth:
        return "user_dev"
    if not _settings.clerk_jwks_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth not configured",
        )
    try:
        jwks = _get_jwks_client()
        signing_key = jwks.get_signing_key_from_jwt(token)
        decode_kwargs: dict = {
            "algorithms": ["RS256"],
            "options": {"verify_aud": False},
        }
        if _settings.clerk_issuer:
            decode_kwargs["issuer"] = _settings.clerk_issuer
        payload = jwt.decode(token, signing_key.key, **decode_kwargs)
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return str(sub)
    except HTTPException:
        raise
    except Exception as e:
        log.warning("jwt_verify_failed", error=str(e))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from e


async def get_current_user_id(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> str:
    if _settings.disable_auth:
        return "user_dev"
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return verify_bearer_token(creds.credentials)
