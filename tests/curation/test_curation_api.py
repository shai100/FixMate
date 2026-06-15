import httpx
import pytest
from httpx import ASGITransport

from fixmate.api.main import app
from tests.api.conftest import auth_headers


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_tech_forbidden_from_queue(client, curation_world):
    w = curation_world
    resp = await client.get("/curation/queue", headers=auth_headers(w.org_id, w.tech_id, "tech"))
    assert resp.status_code == 403


async def test_tech_forbidden_from_approve(client, curation_world):
    w = curation_world
    resp = await client.post(
        f"/fixes/{w.fix_id}/approve",
        json={},
        headers=auth_headers(w.org_id, w.tech_id, "tech"),
    )
    assert resp.status_code == 403


@pytest.mark.integration
async def test_curator_queue_returns_pending_fix(client, curation_world):
    w = curation_world
    resp = await client.get(
        "/curation/queue", headers=auth_headers(w.org_id, w.curator_id, "curator")
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["fix_id"] == str(w.fix_id)
    assert body[0]["prescreen"] is not None


@pytest.mark.integration
async def test_curator_can_approve(client, curation_world):
    w = curation_world
    resp = await client.post(
        f"/fixes/{w.fix_id}/approve",
        json={},
        headers=auth_headers(w.org_id, w.curator_id, "curator"),
    )
    assert resp.status_code == 204


async def test_curator_reject_records_reason(client, curation_world):
    w = curation_world
    resp = await client.post(
        f"/fixes/{w.fix_id}/reject",
        json={"reason": "duplicate"},
        headers=auth_headers(w.org_id, w.curator_id, "curator"),
    )
    assert resp.status_code == 204


async def test_illegal_transition_returns_409(client, curation_world):
    w = curation_world
    headers = auth_headers(w.org_id, w.curator_id, "curator")
    first = await client.post(f"/fixes/{w.fix_id}/reject", json={"reason": "dup"}, headers=headers)
    assert first.status_code == 204
    # Cannot approve a rejected fix — must resubmit (state machine).
    second = await client.post(f"/fixes/{w.fix_id}/approve", json={}, headers=headers)
    assert second.status_code == 409


async def test_cross_tenant_fix_not_found(client, curation_world):
    w = curation_world
    # Org B (with a curator role) cannot resolve org A's fix — RLS hides it.
    resp = await client.post(
        f"/fixes/{w.fix_id}/reject",
        json={"reason": "x"},
        headers=auth_headers(w.other_org_id, w.curator_id, "curator"),
    )
    assert resp.status_code == 404
