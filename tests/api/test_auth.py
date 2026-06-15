import importlib
import uuid

import pytest

from fixmate.api.deps import AuthContext
from tests.api.conftest import auth_headers


async def test_missing_headers_rejected(client):
    resp = await client.post("/conversations", json={})
    assert resp.status_code == 401


async def test_bad_role_rejected(client, org_user):
    org_a, user_id, _ = org_user
    resp = await client.post(
        "/conversations", json={}, headers=auth_headers(org_a, user_id, role="superuser")
    )
    assert resp.status_code == 401


async def test_non_uuid_org_rejected(client, org_user):
    _, user_id, _ = org_user
    headers = {"X-Org-Id": "not-a-uuid", "X-User-Id": str(user_id), "X-Role": "tech"}
    resp = await client.post("/conversations", json={}, headers=headers)
    assert resp.status_code == 401


async def test_health_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_production_dev_auth_is_refused(monkeypatch):
    # The API must refuse to boot with header auth enabled outside local (6.1).
    import fixmate.api.main as main
    from fixmate.core.settings import settings

    monkeypatch.setattr(settings, "dev_auth", True)
    monkeypatch.setattr(settings, "env", "production")
    with pytest.raises(RuntimeError):
        importlib.reload(main)
    # Restore a clean module for any later import.
    monkeypatch.undo()
    importlib.reload(main)


def test_auth_context_shape():
    ctx = AuthContext(org_id=uuid.uuid4(), user_id=uuid.uuid4(), role="tech")
    assert ctx.role == "tech"
