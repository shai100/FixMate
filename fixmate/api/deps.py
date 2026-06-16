"""Authentication and authorization dependencies for the API.

This is the front door for *who is making a request* and *what they may do*.
Every protected endpoint declares ``Depends(get_current_user)`` (or
``Depends(require_role(...))``) and FastAPI runs the relevant function below
before the handler, producing an ``AuthContext`` the handler can trust.

Two auth backends produce the same ``AuthContext`` so handlers never change:
  - **Dev auth** (local only): reads ``X-Org-Id`` / ``X-User-Id`` / ``X-Role``
    headers. Convenient for local work; spoofable, hence locked to ``ENV=local``
    by ``main._guard_auth_config``.
  - **OIDC** (production): validates a Keycloak Bearer token — see
    ``fixmate/api/auth_oidc.py``.

The org id always comes from the verified identity, never from a query/body
param, which is the cornerstone of tenant isolation (CLAUDE.md §6).
"""

import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

from fixmate.core.settings import settings

# The three roles a user can hold, least to most privileged elsewhere.
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
    authorization: str | None = Header(default=None),
) -> AuthContext:
    """FastAPI dependency that resolves the caller's identity into an ``AuthContext``.

    Branches on configuration: when ``dev_auth`` is off it validates the OIDC
    Bearer token; otherwise it reads and validates the dev headers. Either path
    raises ``HTTPException(401)`` on anything missing or malformed, so a handler
    that depends on this is guaranteed a fully-formed, trusted identity.
    """
    if not settings.dev_auth:
        return _oidc_auth(authorization)
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


def _oidc_auth(authorization: str | None) -> AuthContext:
    """Extract and validate the Bearer token from the ``Authorization`` header.

    Delegates the real cryptographic work to the OIDC validator and converts a
    rejected token into a 401.
    """
    # Imported lazily: auth_oidc imports AuthContext/ROLES from this module.
    import jwt

    from fixmate.api.auth_oidc import get_validator

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        return get_validator().validate(token)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc


def require_role(*allowed: str):
    """Build a dependency that allows only the given roles (FR-14).

    Call it with the permitted roles (e.g. ``require_role("curator", "admin")``)
    and use the result as a ``Depends(...)`` on an endpoint. It first resolves
    the identity via ``get_current_user``, then returns it unchanged if the role
    is allowed or raises ``HTTPException(403)`` otherwise. Defined here so the
    entire auth surface lives in one module.
    """

    async def _guard(auth: AuthContext = Depends(get_current_user)) -> AuthContext:
        if auth.role not in allowed:
            raise HTTPException(status_code=403, detail=f"requires role in {allowed}")
        return auth

    return _guard
