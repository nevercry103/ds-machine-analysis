"""JWT-based auth — role scopes (operator / engineer / manager / executive).

Phase 4: real JWT signing and validation using python-jose. Tokens
carry a `role` claim that maps to the permission matrix below.

Token issuance:
  - `create_token(role, secret)` — creates a signed HS256 JWT
  - Tokens expire after `TOKEN_EXPIRE_HOURS` (default 24h)

Token validation:
  - `require_role(allowed, authorization)` — FastAPI dependency
  - Extracts Bearer token, decodes JWT, checks role is in `allowed`
  - Dev mode: no token → defaults to ENGINEER (no-auth convenience)

Environment:
  - `DS_MA_JWT_SECRET` — HMAC secret (required for production)
  - `DS_MA_JWT_DISABLE` — set to "1" to disable auth entirely (dev)

Architecture layer: API MIDDLEWARE
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from enum import StrEnum

from fastapi import Header, HTTPException, status

from utils.logger import log

# JWT secret — required for production. Dev mode uses a fallback.
_JWT_SECRET = os.getenv("DS_MA_JWT_SECRET", "")
_JWT_DISABLED = os.getenv("DS_MA_JWT_DISABLE", "").lower() in ("1", "true", "yes")
_DEV_SECRET = "ds-ma-dev-secret-CHANGE-IN-PRODUCTION"  # noqa: S105

TOKEN_EXPIRE_HOURS = 24
_ALGORITHM = "HS256"


class Role(StrEnum):
    OPERATOR = "operator"
    ENGINEER = "engineer"
    MANAGER = "manager"
    EXECUTIVE = "executive"


# Permission matrix — role × action
_PERMISSIONS: dict[Role, set[str]] = {
    Role.OPERATOR: {"machine:read", "alarm:ack", "downtime:tag", "logbook:read"},
    Role.ENGINEER: {
        "machine:read",
        "machine:configure",
        "alarm:ack",
        "alarm:configure",
        "downtime:tag",
        "cycle:replay",
        "plc:write",
        "logbook:read",
        "logbook:write",
    },
    Role.MANAGER: {"machine:read", "report:export", "downtime:analyze", "logbook:read"},
    Role.EXECUTIVE: {"machine:read", "report:export"},
}


def _get_secret() -> str:
    """Return the JWT secret — env var or dev fallback."""
    if _JWT_SECRET:
        return _JWT_SECRET
    log.warning("DS_MA_JWT_SECRET not set — using dev fallback (NOT for production)")
    return _DEV_SECRET


def create_token(role: str | Role, secret: str | None = None) -> str:
    """Create a signed JWT with the given role claim.

    Returns the encoded token string. Raises ImportError if python-jose
    is not installed.
    """
    from jose import jwt

    secret = secret or _get_secret()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(role),
        "role": str(role),
        "iat": now,
        "exp": now + timedelta(hours=TOKEN_EXPIRE_HOURS),
        "iss": "ds-machine-analyzer",
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def decode_token(token: str, secret: str | None = None) -> dict:
    """Decode and validate a JWT. Returns the payload dict.

    Raises jose.JWTError on invalid/expired tokens.
    """
    from jose import jwt

    secret = secret or _get_secret()
    return jwt.decode(token, secret, algorithms=[_ALGORITHM])


async def require_role(
    *, allowed: set[Role], authorization: str | None = Header(default=None)
) -> Role:
    """FastAPI dependency: parse JWT, return role, raise 403 if not allowed.

    Dev mode (no token and JWT not disabled): returns ENGINEER.
    Production (DS_MA_JWT_SECRET set): requires valid Bearer token.
    """
    # Auth disabled entirely — dev convenience
    if _JWT_DISABLED:
        return Role.ENGINEER

    if authorization is None:
        if not _JWT_SECRET:
            # No secret configured = dev mode, no token required
            return Role.ENGINEER
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract Bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization must be 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = parts[1]

    try:
        payload = decode_token(token)
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="python-jose not installed — JWT validation unavailable",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role_str = payload.get("role", "")
    try:
        role = Role(role_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Unknown role in token: {role_str!r}",
        )

    if role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{role}' is not allowed. Required: {sorted(r.value for r in allowed)}",
        )

    return role


def has_permission(role: Role, action: str) -> bool:
    """Check whether a role can perform an action."""
    return action in _PERMISSIONS.get(role, set())
