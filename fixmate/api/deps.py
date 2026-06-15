import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

from fixmate.core.settings import settings

ROLES = ("tech", "curator", "admin")


@dataclass
class AuthContext:
    """Identity for the current request (Appendix A.6).

    Produced by dev-auth headers here and, from Phase 9, by the OIDC validator —
    handlers depend on this dataclass, not on how it was built. The org id always
    comes from the authenticated identity, never from a query param (CLAUDE.md §6).
    """

    org_id: uuid.UUID
    user_id: uuid.UUID
    role: str


async def get_current_user(
    x_org_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    x_role: str | None = Header(default=None),
) -> AuthContext:
    if not settings.dev_auth:
        # Phase 9 wires the Keycloak OIDC validator in here.
        raise HTTPException(status_code=501, detail="OIDC auth not yet implemented (Phase 9)")
    if not (x_org_id and x_user_id and x_role):
        raise HTTPException(status_code=401, detail="Missing X-Org-Id / X-User-Id / X-Role headers")
    try:
        org_id = uuid.UUID(x_org_id)
        user_id = uuid.UUID(x_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="X-Org-Id / X-User-Id must be UUIDs") from exc
    if x_role not in ROLES:
        raise HTTPException(status_code=401, detail=f"X-Role must be one of {ROLES}")
    return AuthContext(org_id=org_id, user_id=user_id, role=x_role)


def require_role(*allowed: str):
    """Dependency factory guarding an endpoint by role (FR-14).

    Used from Phase 8 for curator/admin-only actions; defined here so the auth
    surface lives in one place.
    """

    async def _guard(auth: AuthContext = Depends(get_current_user)) -> AuthContext:
        if auth.role not in allowed:
            raise HTTPException(status_code=403, detail=f"requires role in {allowed}")
        return auth

    return _guard
