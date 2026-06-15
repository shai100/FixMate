import uuid

from tests.api.conftest import auth_headers


async def test_create_and_get_conversation(client, org_user):
    org_a, user_id, _ = org_user
    headers = auth_headers(org_a, user_id)

    created = await client.post("/conversations", json={}, headers=headers)
    assert created.status_code == 201
    conv_id = created.json()["id"]

    fetched = await client.get(f"/conversations/{conv_id}", headers=headers)
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["id"] == conv_id
    assert body["messages"] == []


async def test_get_missing_conversation_404(client, org_user):
    org_a, user_id, _ = org_user
    resp = await client.get(f"/conversations/{uuid.uuid4()}", headers=auth_headers(org_a, user_id))
    assert resp.status_code == 404


async def test_cross_tenant_conversation_is_404(client, org_user):
    # RLS proves itself through the API: org B cannot see org A's conversation.
    org_a, user_id, org_b = org_user
    created = await client.post("/conversations", json={}, headers=auth_headers(org_a, user_id))
    conv_id = created.json()["id"]

    # Any well-formed identity under org B; the row is invisible under B's RLS scope.
    resp = await client.get(f"/conversations/{conv_id}", headers=auth_headers(org_b, uuid.uuid4()))
    assert resp.status_code == 404
