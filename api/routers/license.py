"""License / tier endpoints — read-only.

The PWA shows the loaded tier in the navbar (so engineers know whether
e.g. Replay Mode is available) and uses feature flags to grey-out
disabled UI surfaces. The platform is single-tenant per process — no
endpoint changes the tier; that requires a license-key swap + restart.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.middleware.auth import Role, create_token
from api.state import AppState
from core.tier_profile import TierProfile, list_available_tiers

router = APIRouter(prefix="/api/license", tags=["license"])


def _state(request: Request) -> AppState:
    state: AppState | None = getattr(request.app.state, "app_state", None)
    if state is None:
        raise HTTPException(status_code=503, detail="App state not initialized")
    return state


@router.get("")
async def get_license(request: Request) -> dict:
    state = _state(request)
    tier: TierProfile | None = state.registry.tier
    if tier is None:
        return {
            "tier_id": None,
            "display_name": "(unlicensed dev mode)",
            "max_machines": state.registry.MAX_MACHINES,
            "current_machines": len(state.registry),
            "features": {},
            "replay_retention_hours": 0,
            "available_tiers": list_available_tiers(),
        }
    return {
        "tier_id": tier.tier_id,
        "display_name": tier.display_name,
        "description": tier.description,
        "max_machines": tier.max_machines,
        "max_steps_per_machine": tier.max_steps_per_machine,
        "current_machines": len(state.registry),
        "features": tier.features.model_dump(),
        "replay_retention_hours": tier.replay_retention_hours,
        "data_retention_days": tier.data_retention_days,
        "available_tiers": list_available_tiers(),
    }


class TokenRequest(BaseModel):
    """Request body for token creation."""
    role: str = Field(..., description="operator | engineer | manager | executive")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    expires_hours: int


@router.post("/token", response_model=TokenResponse)
async def create_auth_token(body: TokenRequest) -> TokenResponse:
    """Issue a JWT for the given role.

    In production this would be behind an admin auth gate or replaced
    by SSO/LDAP integration. For now it's open so engineers can test
    role-based access on the PWA and desktop.
    """
    try:
        role = Role(body.role.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown role {body.role!r}. Allowed: {[r.value for r in Role]}",
        )
    try:
        token = create_token(role)
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="python-jose not installed — cannot create tokens",
        )
    return TokenResponse(
        access_token=token,
        role=role.value,
        expires_hours=24,
    )
