from tests.api.conftest import auth_headers


async def test_create_and_list_equipment(client, org_user):
    org_a, user_id, _ = org_user
    headers = auth_headers(org_a, user_id)

    created = await client.post(
        "/equipment",
        json={"name": "Pump X", "manufacturer": "Acme", "model": "PX-100"},
        headers=headers,
    )
    assert created.status_code == 201
    assert created.json()["name"] == "Pump X"

    listed = await client.get("/equipment", headers=headers)
    assert listed.status_code == 200
    names = [e["name"] for e in listed.json()]
    assert "Pump X" in names


async def test_equipment_is_tenant_scoped(client, org_user):
    org_a, user_id, org_b = org_user
    await client.post("/equipment", json={"name": "Pump X"}, headers=auth_headers(org_a, user_id))
    import uuid

    other = await client.get("/equipment", headers=auth_headers(org_b, uuid.uuid4()))
    assert other.status_code == 200
    assert other.json() == []
