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


async def test_positive_feedback_endpoint(client, feedback_world):
    w = feedback_world
    resp = await client.post(
        f"/messages/{w.message_id}/feedback",
        json={"helped": True},
        headers=auth_headers(w.org_id, w.user_id),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["helped"] is True
    assert body["fix_id"] is None
    assert body["feedback_id"]


async def test_negative_feedback_with_fix_endpoint(client, feedback_world):
    w = feedback_world
    resp = await client.post(
        f"/messages/{w.message_id}/feedback",
        json={"helped": False, "fix_text": "Swap the seal, part AB-1234."},
        headers=auth_headers(w.org_id, w.user_id),
    )
    assert resp.status_code == 201
    assert resp.json()["fix_id"]


async def test_cross_tenant_message_404(client, feedback_world):
    w = feedback_world
    # Org B cannot leave feedback on org A's message — RLS hides it (CLAUDE.md §6).
    resp = await client.post(
        f"/messages/{w.message_id}/feedback",
        json={"helped": True},
        headers=auth_headers(w.other_org_id, w.user_id),
    )
    assert resp.status_code == 404
