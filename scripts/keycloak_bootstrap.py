"""Bootstrap the Keycloak realm FixMate's OIDC backend expects (Phase 9).

Idempotent: safe to re-run. Creates the `fixmate` realm, a public `fixmate-api`
client with direct-access (password) grants for local testing, the realm roles
tech/curator/admin, an `organization_id` user-attribute → access-token claim
mapper, and three test users (one per role) carrying that org id.

Run after `docker compose --profile auth up -d`:
    python scripts/keycloak_bootstrap.py
"""

import sys
import uuid

import httpx

from fixmate.core.settings import settings

BASE = settings.keycloak_base_url
REALM = settings.keycloak_realm
CLIENT_ID = settings.oidc_client_id
ADMIN_USER = "admin"
ADMIN_PASS = "admin"

# Test users share one tenant so password-grant tokens carry a real org id.
# Phase 12's seed_demo can reuse this id to align Keycloak identities with DB rows.
DEMO_ORG_ID = "00000000-0000-0000-0000-0000000000d0"
TEST_USERS = [
    ("tech@example.com", "tech", "tech"),
    ("curator@example.com", "curator", "curator"),
    ("admin@example.com", "admin", "admin"),
]


def _admin_token(c: httpx.Client) -> str:
    r = c.post(
        f"{BASE}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": ADMIN_USER,
            "password": ADMIN_PASS,
        },
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _ensure_realm(c: httpx.Client) -> None:
    if c.get(f"{BASE}/admin/realms/{REALM}").status_code == 200:
        print(f"realm {REALM!r} exists")
        return
    c.post(f"{BASE}/admin/realms", json={"realm": REALM, "enabled": True}).raise_for_status()
    print(f"created realm {REALM!r}")


def _enable_unmanaged_attributes(c: httpx.Client) -> None:
    # Keycloak 26 drops user attributes not declared in the user profile unless the
    # realm opts into unmanaged attributes — without this, organization_id is lost
    # and never reaches the access token.
    url = f"{BASE}/admin/realms/{REALM}/users/profile"
    profile = c.get(url).json()
    if profile.get("unmanagedAttributePolicy") == "ENABLED":
        print("unmanaged attributes already enabled")
        return
    profile["unmanagedAttributePolicy"] = "ENABLED"
    c.put(url, json=profile).raise_for_status()
    print("enabled unmanaged attributes")


def _ensure_client(c: httpx.Client) -> str:
    existing = c.get(f"{BASE}/admin/realms/{REALM}/clients", params={"clientId": CLIENT_ID}).json()
    if existing:
        cid = existing[0]["id"]
        print(f"client {CLIENT_ID!r} exists")
    else:
        c.post(
            f"{BASE}/admin/realms/{REALM}/clients",
            json={
                "clientId": CLIENT_ID,
                "enabled": True,
                "publicClient": True,
                "directAccessGrantsEnabled": True,
                "standardFlowEnabled": True,
                "redirectUris": ["*"],
                "webOrigins": ["*"],
            },
        ).raise_for_status()
        cid = c.get(
            f"{BASE}/admin/realms/{REALM}/clients", params={"clientId": CLIENT_ID}
        ).json()[0]["id"]
        print(f"created client {CLIENT_ID!r}")
    _ensure_org_mapper(c, cid)
    return cid


def _ensure_org_mapper(c: httpx.Client, client_uuid: str) -> None:
    mappers = c.get(
        f"{BASE}/admin/realms/{REALM}/clients/{client_uuid}/protocol-mappers/models"
    ).json()
    if any(m["name"] == "organization_id" for m in mappers):
        print("  org-id mapper exists")
        return
    c.post(
        f"{BASE}/admin/realms/{REALM}/clients/{client_uuid}/protocol-mappers/models",
        json={
            "name": "organization_id",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-usermodel-attribute-mapper",
            "config": {
                "user.attribute": "organization_id",
                "claim.name": "organization_id",
                "jsonType.label": "String",
                "id.token.claim": "true",
                "access.token.claim": "true",
                "userinfo.token.claim": "true",
            },
        },
    ).raise_for_status()
    print("  created org-id mapper")


def _ensure_roles(c: httpx.Client) -> None:
    for role in ("tech", "curator", "admin"):
        if c.get(f"{BASE}/admin/realms/{REALM}/roles/{role}").status_code == 200:
            continue
        c.post(f"{BASE}/admin/realms/{REALM}/roles", json={"name": role}).raise_for_status()
        print(f"created role {role!r}")


def _ensure_user(c: httpx.Client, email: str, role: str, password: str) -> None:
    # firstName/lastName + empty requiredActions are needed or Keycloak 26's
    # "Verify Profile" action rejects the password grant with "not fully set up".
    body = {
        "username": email,
        "email": email,
        "firstName": role.capitalize(),
        "lastName": "Tester",
        "enabled": True,
        "emailVerified": True,
        "requiredActions": [],
        "attributes": {"organization_id": [DEMO_ORG_ID]},
    }
    existing = c.get(f"{BASE}/admin/realms/{REALM}/users", params={"email": email}).json()
    if existing:
        user_id = existing[0]["id"]
        c.put(f"{BASE}/admin/realms/{REALM}/users/{user_id}", json=body).raise_for_status()
        print(f"user {email!r} exists (updated)")
    else:
        c.post(
            f"{BASE}/admin/realms/{REALM}/users",
            json={**body, "credentials": [{"type": "password", "value": password, "temporary": False}]},
        ).raise_for_status()
        user_id = c.get(f"{BASE}/admin/realms/{REALM}/users", params={"email": email}).json()[0][
            "id"
        ]
        print(f"created user {email!r}")
    c.put(
        f"{BASE}/admin/realms/{REALM}/users/{user_id}/reset-password",
        json={"type": "password", "value": password, "temporary": False},
    ).raise_for_status()
    role_repr = c.get(f"{BASE}/admin/realms/{REALM}/roles/{role}").json()
    c.post(
        f"{BASE}/admin/realms/{REALM}/users/{user_id}/role-mappings/realm",
        json=[{"id": role_repr["id"], "name": role_repr["name"]}],
    ).raise_for_status()


def main() -> None:
    uuid.UUID(DEMO_ORG_ID)  # fail fast if the constant is malformed
    with httpx.Client(timeout=15) as c:
        token = _admin_token(c)
        c.headers["Authorization"] = f"Bearer {token}"
        _ensure_realm(c)
        _enable_unmanaged_attributes(c)
        _ensure_client(c)
        _ensure_roles(c)
        for email, role, password in TEST_USERS:
            _ensure_user(c, email, role, password)
    print(f"\nDone. Realm {REALM!r}, client {CLIENT_ID!r}, demo org {DEMO_ORG_ID}")
    print("Test users (password = role name): " + ", ".join(e for e, _, _ in TEST_USERS))


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPError as exc:
        print(f"bootstrap failed: {exc}", file=sys.stderr)
        sys.exit(1)
