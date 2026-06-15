import datetime
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from fixmate.api.auth_oidc import claims_to_context, decode_token

ISSUER = "http://localhost:8080/realms/fixmate"


@pytest.fixture(scope="module")
def keypair():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private, private.public_key()


def _token(private_key, claims: dict, *, expired: bool = False) -> str:
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    payload = {
        "iss": ISSUER,
        "sub": str(uuid.uuid4()),
        "iat": now,
        "exp": now - datetime.timedelta(minutes=5) if expired else now + datetime.timedelta(minutes=5),
        **claims,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def _decode(token, public_key):
    return decode_token(token, public_key, issuer=ISSUER)


def test_valid_token_maps_to_auth_context(keypair):
    private, public = keypair
    org_id = uuid.uuid4()
    token = _token(
        private,
        {"organization_id": str(org_id), "realm_access": {"roles": ["tech", "offline_access"]}},
    )
    ctx = _decode(token, public)
    assert ctx.org_id == org_id
    assert ctx.role == "tech"


def test_role_claim_maps_highest_privilege(keypair):
    private, public = keypair
    token = _token(
        private,
        {"organization_id": str(uuid.uuid4()), "realm_access": {"roles": ["tech", "curator"]}},
    )
    assert _decode(token, public).role == "curator"


def test_missing_org_claim_rejected(keypair):
    private, public = keypair
    token = _token(private, {"realm_access": {"roles": ["tech"]}})
    with pytest.raises(jwt.InvalidTokenError):
        _decode(token, public)


def test_no_fixmate_role_rejected(keypair):
    private, public = keypair
    token = _token(
        private,
        {"organization_id": str(uuid.uuid4()), "realm_access": {"roles": ["offline_access"]}},
    )
    with pytest.raises(jwt.InvalidTokenError):
        _decode(token, public)


def test_expired_token_rejected(keypair):
    private, public = keypair
    token = _token(
        private,
        {"organization_id": str(uuid.uuid4()), "realm_access": {"roles": ["tech"]}},
        expired=True,
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        _decode(token, public)


def test_garbage_token_rejected(keypair):
    _, public = keypair
    with pytest.raises(jwt.InvalidTokenError):
        _decode("not.a.jwt", public)


def test_wrong_signing_key_rejected(keypair):
    private, _ = keypair
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key()
    token = _token(
        private,
        {"organization_id": str(uuid.uuid4()), "realm_access": {"roles": ["tech"]}},
    )
    with pytest.raises(jwt.InvalidTokenError):
        _decode(token, other)


def test_wrong_issuer_rejected(keypair):
    private, public = keypair
    token = _token(
        private,
        {
            "iss": "http://evil/realms/fixmate",
            "organization_id": str(uuid.uuid4()),
            "realm_access": {"roles": ["tech"]},
        },
    )
    with pytest.raises(jwt.InvalidTokenError):
        _decode(token, public)


def test_claims_to_context_pure():
    org_id, sub = uuid.uuid4(), uuid.uuid4()
    ctx = claims_to_context(
        {"organization_id": str(org_id), "sub": str(sub), "realm_access": {"roles": ["admin"]}}
    )
    assert (ctx.org_id, ctx.user_id, ctx.role) == (org_id, sub, "admin")


async def test_oidc_branch_rejects_missing_bearer(monkeypatch):
    # When dev_auth is off, get_current_user defers to OIDC; a request with no
    # Bearer token is a 401 (and never reaches the network).
    from fastapi import HTTPException

    from fixmate.api import deps
    from fixmate.core.settings import settings

    monkeypatch.setattr(settings, "dev_auth", False)
    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user(authorization=None)
    assert exc.value.status_code == 401


@pytest.mark.integration
def test_password_grant_flow_against_live_keycloak():
    """One real password-grant flow against local Keycloak (plan 9.3).

    Requires: docker compose --profile auth up -d && python scripts/keycloak_bootstrap.py
    """
    import httpx

    from fixmate.api.auth_oidc import get_validator
    from fixmate.core.settings import settings

    token_url = (
        f"{settings.keycloak_base_url}/realms/{settings.keycloak_realm}"
        "/protocol/openid-connect/token"
    )
    resp = httpx.post(
        token_url,
        data={
            "grant_type": "password",
            "client_id": settings.oidc_client_id,
            "username": "tech@example.com",
            "password": "tech",
        },
        timeout=10,
    )
    resp.raise_for_status()
    access_token = resp.json()["access_token"]
    ctx = get_validator().validate(access_token)
    assert ctx.role == "tech"
    assert isinstance(ctx.org_id, uuid.UUID)
