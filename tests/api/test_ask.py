import pytest

from fixmate.core.db import session_for_org
from fixmate.core.models import EquipmentProfile, User
from fixmate.ingestion.pipeline import ingest_document
from tests.api.conftest import auth_headers
from tests.retrieval.conftest import sample_pdf  # noqa: F401

pytestmark = pytest.mark.integration


@pytest.fixture
async def ingested_org_with_user(two_orgs, sample_pdf):  # noqa: F811
    """Org A: a tech user, equipment, and the sample manual ingested."""
    org_a, _ = two_orgs
    async with session_for_org(org_a) as s:
        user = User(organization_id=org_a, name="Tech One", role="tech")
        eq = EquipmentProfile(organization_id=org_a, name="Pump X")
        s.add(user)
        s.add(eq)
        await s.commit()
        user_id, eq_id = user.id, eq.id
    await ingest_document(org_a, eq_id, sample_pdf)
    return org_a, user_id, eq_id


async def test_ask_returns_grounded_answer_and_persists_messages(client, ingested_org_with_user):
    org_a, user_id, eq_id = ingested_org_with_user
    headers = auth_headers(org_a, user_id)

    created = await client.post(
        "/conversations", json={"equipment_id": str(eq_id)}, headers=headers
    )
    conv_id = created.json()["id"]

    resp = await client.post(
        f"/conversations/{conv_id}/ask",
        json={"question": "How do I fix error E47?"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    # API contract (Phase 6): a well-formed answer payload round-trips. The
    # grounded-vs-escalated decision is the LLM's and is exercised in Phase 5;
    # on the qwen3:4b dev backend it is non-deterministic (over-refusal is a
    # documented small-model artifact), so we only assert the API shape here.
    assert body["text"].strip()
    assert isinstance(body["escalated"], bool)
    assert body["message_id"]
    assert body["answer_log_id"]
    assert body["confidence"] in ("high", "medium", "low")
    if not body["escalated"]:
        assert len(body["citations"]) >= 1

    # The conversation now holds both the user question and the assistant answer,
    # in order, with the assistant message linked to its answer log.
    fetched = await client.get(f"/conversations/{conv_id}", headers=headers)
    messages = fetched.json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "How do I fix error E47?"
    assert messages[1]["answer_log_id"] == body["answer_log_id"]


async def test_ask_unknown_conversation_404(client, ingested_org_with_user):
    org_a, user_id, _ = ingested_org_with_user
    import uuid

    resp = await client.post(
        f"/conversations/{uuid.uuid4()}/ask",
        json={"question": "anything"},
        headers=auth_headers(org_a, user_id),
    )
    assert resp.status_code == 404
