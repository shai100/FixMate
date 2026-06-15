"""Keycloak OIDC Bearer-token validation (Phase 9).

Replaces the spoofable dev-auth headers (Phase 6) with real JWT validation against
the realm's published JWKS. The output is the same `AuthContext` dataclass the rest
of the API already depends on (Appendix A.6), so handlers are untouched when the
backend flips from `DEV_AUTH=true` to OIDC.
"""

import functools
import uuid

import jwt
from jwt import PyJWKClient

from fixmate.api.deps import ROLES, AuthContext
from fixmate.core.settings import settings

# Highest privilege first: a token may carry several realm roles; we grant the
# most privileged FixMate role present (admin > curator > tech).
_ROLE_PRECEDENCE = ("admin", "curator", "tech")


def _extract_role(claims: dict) -> str | None:
    granted = set(claims.get("realm_access", {}).get("roles", []))
    return next((r for r in _ROLE_PRECEDENCE if r in granted), None)


def claims_to_context(claims: dict) -> AuthContext:
    """Map verified JWT claims to an AuthContext, rejecting incomplete tokens.

    Raises jwt.InvalidTokenError (the call site turns this into a 401) when the
    org id, subject, or a FixMate role is missing — a token without tenancy or a
    role must never reach business logic.
    """
    org = claims.get("organization_id")
    if not org:
        raise jwt.InvalidTokenError("token missing organization_id claim")
    sub = claims.get("sub")
    if not sub:
        raise jwt.InvalidTokenError("token missing sub claim")
    role = _extract_role(claims)
    if role is None:
        raise jwt.InvalidTokenError(f"token carries no FixMate role (one of {ROLES})")
    try:
        org_id = uuid.UUID(org)
        user_id = uuid.UUID(sub)
    except ValueError as exc:
        raise jwt.InvalidTokenError("organization_id / sub must be UUIDs") from exc
    return AuthContext(org_id=org_id, user_id=user_id, role=role)


def decode_token(
    token: str,
    key,
    *,
    issuer: str,
    audience: str | None = None,
    verify_audience: bool = False,
) -> AuthContext:
    """Verify signature + standard claims with a known public key, then map.

    Separated from JWKS fetching so it can be unit-tested with a locally generated
    keypair (no live Keycloak). Signature, expiry, and issuer are always enforced.
    """
    claims = jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        issuer=issuer,
        audience=audience if verify_audience else None,
        options={"verify_aud": verify_audience},
    )
    return claims_to_context(claims)


class OIDCValidator:
    def __init__(
        self,
        jwks_uri: str,
        issuer: str,
        *,
        audience: str | None = None,
        verify_audience: bool = False,
    ):
        # PyJWKClient caches fetched signing keys (key rotation is picked up on
        # cache miss), so we resolve the realm's public key without a network
        # round-trip per request.
        self._jwks = PyJWKClient(jwks_uri)
        self._issuer = issuer
        self._audience = audience
        self._verify_audience = verify_audience

    def validate(self, token: str) -> AuthContext:
        signing_key = self._jwks.get_signing_key_from_jwt(token).key
        return decode_token(
            token,
            signing_key,
            issuer=self._issuer,
            audience=self._audience,
            verify_audience=self._verify_audience,
        )


def issuer_url() -> str:
    return f"{settings.keycloak_base_url}/realms/{settings.keycloak_realm}"


@functools.lru_cache(maxsize=1)
def get_validator() -> OIDCValidator:
    issuer = issuer_url()
    return OIDCValidator(
        jwks_uri=f"{issuer}/protocol/openid-connect/certs",
        issuer=issuer,
        audience=settings.oidc_client_id,
        verify_audience=settings.oidc_verify_audience,
    )
