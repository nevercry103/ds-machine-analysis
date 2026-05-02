"""JWT-based auth — role scopes (operator / engineer / manager / executive).

Stub for Phase 1: shape only, no real signing. Replaced with real
implementation when first multi-role customer ships (Phase 4).
"""

from __future__ import annotations

from enum import StrEnum

from fastapi import Header, HTTPException, status


class Role(StrEnum):
    OPERATOR = "operator"
    ENGINEER = "engineer"
    MANAGER = "manager"
    EXECUTIVE = "executive"


# Permission matrix — role × action
_PERMISSIONS: dict[Role, set[str]] = {
    Role.OPERATOR: {"machine:read", "alarm:ack", "downtime:tag"},
    Role.ENGINEER: {
        "machine:read",
        "machine:configure",
        "alarm:ack",
        "alarm:configure",
        "downtime:tag",
        "cycle:replay",
        "plc:write",  # restricted via UI confirmation
    },
    Role.MANAGER: {"machine:read", "report:export", "downtime:analyze"},
    Role.EXECUTIVE: {"machine:read", "report:export"},
}


async def require_role(
    *, allowed: set[Role], authorization: str | None = Header(default=None)
) -> Role:
    """FastAPI dependency: parse JWT, return role, raise 403 if not allowed.

    TODO Phase 1: real JWT validation. For now, returns ENGINEER if no token
    (dev mode).
    """
    if authorization is None:
        return Role.ENGINEER  # dev-mode default

    # TODO: jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="JWT auth not implemented yet (Phase 1 stub)",
    )


def has_permission(role: Role, action: str) -> bool:
    """Check whether a role can perform an action."""
    return action in _PERMISSIONS.get(role, set())
