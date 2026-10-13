from __future__ import annotations

from fastapi import Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from server.core.config import settings

security = HTTPBearer(auto_error=False)

def authenticate_api_key(token: str | None) -> str:
    """Apply the shared REST and MCP API-key policy to a presented token."""
    expected_key = settings.API_AUTH_KEY
    if not expected_key:
        if settings.ENVIRONMENT == "production" or not settings.ALLOW_ANONYMOUS_DEV:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: server has no valid API_AUTH_KEY configured",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return "anonymous"

    if not token or token != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> str:
    """Verify that incoming request provides a valid API token via Bearer header or X-API-Key."""
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    elif x_api_key:
        token = x_api_key

    return authenticate_api_key(token)
