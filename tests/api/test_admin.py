import uuid

import pytest

from fixmate.core.db import session_for_org
from fixmate.core.models import Document, EquipmentProfile, User
from tests.api.conftest import auth_headers


@pytest.fixture
async def org_with_users(two_orgs):
    """Org A with an admin, a curator, and a tech. Returns ids + org B."""
    org_a, org_b = two_orgs
    async with session_for_org(org_a) as s:
        admin = User(organization_id=org_a, name="Admin", role="admin")
        curator = User(organization_id=org_a, name="Cura", role="curator")
        tech = User(organization_id=org_a, name="Tech", role="tech")
        s.add_all([admin, curator, tech])
        await s.commit()
        return org_a, admin.id, curator.id, tech.id, org_b


async def test_admin_lists_users(client, org_with_users):
    org_a, admin_id, *_ = org_with_users
    resp = await client.get("/admin/users", headers=auth_headers(org_a, admin_id, "admin"))
    assert resp.status_code == 200
    roles = sorted(u["role"] for u in resp.json())
    assert roles == ["admin", "curator", "tech"]


async def test_non_admin_forbidden_from_users(client, org_with_users):
    org_a, _, curator_id, tech_id, _ = org_with_users
    for uid, role in ((curator_id, "curator"), (tech_id, "tech")):
        resp = await client.get("/admin/users", headers=auth_headers(org_a, uid, role))
        assert resp.status_code == 403


async def test_admin_sets_role_and_audits(client, org_with_users):
    org_a, admin_id, _, tech_id, _ = org_with_users
    resp = await client.post(
        f"/admin/users/{tech_id}/role",
        json={"role": "curator"},
        headers=auth_headers(org_a, admin_id, "admin"),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "curator"

    # The promoted user is now a reviewer and can reach the curation queue.
    queue = await client.get("/curation/queue", headers=auth_headers(org_a, tech_id, "curator"))
    assert queue.status_code == 200


async def test_set_role_rejects_unknown_role(client, org_with_users):
    org_a, admin_id, _, tech_id, _ = org_with_users
    resp = await client.post(
        f"/admin/users/{tech_id}/role",
        json={"role": "superuser"},
        headers=auth_headers(org_a, admin_id, "admin"),
    )
    assert resp.status_code == 422


async def test_set_role_cross_tenant_is_404(client, org_with_users):
    org_a, _, _, tech_id, org_b = org_with_users
    resp = await client.post(
        f"/admin/users/{tech_id}/role",
        json={"role": "curator"},
        headers=auth_headers(org_b, uuid.uuid4(), "admin"),
    )
    assert resp.status_code == 404


async def test_documents_list_is_tenant_scoped(client, org_with_users):
    org_a, admin_id, _, _, org_b = org_with_users
    async with session_for_org(org_a) as s:
        eq = EquipmentProfile(organization_id=org_a, name="Pump X")
        s.add(eq)
        await s.flush()
        s.add(
            Document(
                organization_id=org_a,
                equipment_id=eq.id,
                title="Pump X Manual",
                version=1,
                storage_key=f"{org_a}/docs/pump.pdf",
            )
        )
        await s.commit()

    listed = await client.get("/documents", headers=auth_headers(org_a, admin_id, "admin"))
    assert listed.status_code == 200
    titles = [d["title"] for d in listed.json()]
    assert "Pump X Manual" in titles

    other = await client.get("/documents", headers=auth_headers(org_b, uuid.uuid4(), "admin"))
    assert other.status_code == 200
    assert other.json() == []
