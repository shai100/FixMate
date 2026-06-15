import pytest

from fixmate.core.db import session_for_org
from fixmate.core.models import EquipmentProfile, User
from tests.api.conftest import auth_headers
from tests.retrieval.conftest import sample_pdf  # noqa: F401

pytestmark = pytest.mark.integration


@pytest.fixture
async def org_user_equipment(two_orgs):
    org_a, _ = two_orgs
    async with session_for_org(org_a) as s:
        user = User(organization_id=org_a, name="Admin", role="admin")
        eq = EquipmentProfile(organization_id=org_a, name="Pump X")
        s.add(user)
        s.add(eq)
        await s.commit()
        return org_a, user.id, eq.id


async def test_upload_enqueues_and_status_reports(client, org_user_equipment, sample_pdf):  # noqa: F811
    org_a, user_id, eq_id = org_user_equipment
    headers = auth_headers(org_a, user_id, role="admin")

    with open(sample_pdf, "rb") as fh:
        resp = await client.post(
            "/documents/upload",
            headers=headers,
            files={"file": ("sample-manual.pdf", fh, "application/pdf")},
            data={"equipment_id": str(eq_id), "title": "Pump X Manual"},
        )
    assert resp.status_code == 202
    task_id = resp.json()["task_id"]
    assert resp.json()["status"] == "queued"

    # Status is queryable immediately (no worker required — PENDING until a
    # worker picks it up; the broker is the live Redis from compose).
    status = await client.get(f"/documents/{task_id}", headers=headers)
    assert status.status_code == 200
    assert status.json()["status"] in ("pending", "queued", "started", "ingested")


async def test_upload_rejects_non_pdf(client, org_user_equipment):
    org_a, user_id, eq_id = org_user_equipment
    headers = auth_headers(org_a, user_id, role="admin")
    resp = await client.post(
        "/documents/upload",
        headers=headers,
        files={"file": ("notes.txt", b"hello", "text/plain")},
        data={"equipment_id": str(eq_id)},
    )
    assert resp.status_code == 400


async def test_upload_rejects_bad_equipment_id(client, org_user_equipment):
    org_a, user_id, _ = org_user_equipment
    headers = auth_headers(org_a, user_id, role="admin")
    resp = await client.post(
        "/documents/upload",
        headers=headers,
        files={"file": ("m.pdf", b"%PDF-1.4 fake", "application/pdf")},
        data={"equipment_id": "not-a-uuid"},
    )
    assert resp.status_code == 422
