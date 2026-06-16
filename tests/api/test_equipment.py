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


async def test_update_equipment_sets_details(client, org_user):
    org_a, user_id, _ = org_user
    headers = auth_headers(org_a, user_id)
    created = await client.post("/equipment", json={"name": "Pump X"}, headers=headers)
    eq_id = created.json()["id"]

    updated = await client.patch(
        f"/equipment/{eq_id}",
        json={"name": "Pump X2", "manufacturer": "Acme", "model": "PX-200"},
        headers=headers,
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["name"] == "Pump X2"
    assert body["manufacturer"] == "Acme"
    assert body["model"] == "PX-200"


async def test_get_and_delete_equipment(client, org_user):
    org_a, user_id, _ = org_user
    headers = auth_headers(org_a, user_id)
    created = await client.post("/equipment", json={"name": "Pump X"}, headers=headers)
    eq_id = created.json()["id"]

    got = await client.get(f"/equipment/{eq_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["id"] == eq_id

    deleted = await client.delete(f"/equipment/{eq_id}", headers=headers)
    assert deleted.status_code == 204

    gone = await client.get(f"/equipment/{eq_id}", headers=headers)
    assert gone.status_code == 404


async def test_equipment_is_tenant_scoped(client, org_user):
    org_a, user_id, org_b = org_user
    await client.post("/equipment", json={"name": "Pump X"}, headers=auth_headers(org_a, user_id))
    import uuid

    other = await client.get("/equipment", headers=auth_headers(org_b, uuid.uuid4()))
    assert other.status_code == 200
    assert other.json() == []
