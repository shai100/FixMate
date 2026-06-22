import pytest

from fixmate.core.db import session_for_org
from fixmate.core.models import Document, EquipmentProfile, User
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
    assert status.json()["status"] in (
        "pending",
        "queued",
        "started",
        "processing",
        "ingested",
    )


async def _make_document(org_a, eq_id, title="Manual") -> str:
    async with session_for_org(org_a) as s:
        doc = Document(
            organization_id=org_a,
            equipment_id=eq_id,
            title=title,
            storage_key=f"{org_a}/docs/{title}.pdf",
        )
        s.add(doc)
        await s.commit()
        return str(doc.id)


async def test_list_documents_filtered_by_equipment(client, org_user_equipment):
    org_a, user_id, eq_id = org_user_equipment
    headers = auth_headers(org_a, user_id, role="admin")
    doc_id = await _make_document(org_a, eq_id)

    listed = await client.get(f"/documents?equipment_id={eq_id}", headers=headers)
    assert listed.status_code == 200
    assert [d["id"] for d in listed.json()] == [doc_id]


async def test_update_document_title(client, org_user_equipment):
    org_a, user_id, eq_id = org_user_equipment
    headers = auth_headers(org_a, user_id, role="admin")
    doc_id = await _make_document(org_a, eq_id, title="Old Title")

    updated = await client.patch(
        f"/documents/{doc_id}", json={"title": "New Title"}, headers=headers
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "New Title"


async def test_delete_document(client, org_user_equipment):
    org_a, user_id, eq_id = org_user_equipment
    headers = auth_headers(org_a, user_id, role="admin")
    doc_id = await _make_document(org_a, eq_id)

    deleted = await client.delete(f"/documents/{doc_id}", headers=headers)
    assert deleted.status_code == 204

    listed = await client.get("/documents", headers=headers)
    assert doc_id not in [d["id"] for d in listed.json()]


async def test_download_document_returns_pdf(client, org_user_equipment):
    org_a, user_id, eq_id = org_user_equipment
    headers = auth_headers(org_a, user_id, role="admin")
    from fixmate.core import storage

    key = storage.put_object(org_a, "docs/download-me.pdf", b"%PDF-1.4 hello", "application/pdf")
    async with session_for_org(org_a) as s:
        doc = Document(
            organization_id=org_a, equipment_id=eq_id, title="Download Me", storage_key=key
        )
        s.add(doc)
        await s.commit()
        doc_id = str(doc.id)

    resp = await client.get(f"/documents/{doc_id}/download", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "Download Me.pdf" in resp.headers["content-disposition"]
    assert resp.content == b"%PDF-1.4 hello"


async def test_download_missing_document_404(client, org_user_equipment):
    import uuid as _uuid

    org_a, user_id, _ = org_user_equipment
    headers = auth_headers(org_a, user_id, role="admin")
    resp = await client.get(f"/documents/{_uuid.uuid4()}/download", headers=headers)
    assert resp.status_code == 404


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
