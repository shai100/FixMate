import asyncio
import uuid

import pytest

from fixmate.core.db import session_for_org
from fixmate.core.models import Document, EquipmentProfile
from fixmate.ingestion.tasks import ingest_document_task

pytestmark = pytest.mark.integration


async def _make_equipment(org_id):
    async with session_for_org(org_id) as s:
        eq = EquipmentProfile(organization_id=org_id, name="Pump X")
        s.add(eq)
        await s.commit()
        return eq.id


def test_task_is_registered():
    assert "fixmate.ingestion.ingest_document" in ingest_document_task.app.tasks


async def test_task_executes_pipeline(two_orgs, sample_pdf):
    org_id, _ = two_orgs
    eq_id = await _make_equipment(org_id)

    # .apply() runs the task body in-process (no broker/worker required) — a
    # smoke test of the Celery wiring through to a persisted document. Run it in
    # a worker thread: the task's ingest_document_sync calls asyncio.run, which
    # can't nest inside this test's running event loop.
    result = await asyncio.to_thread(
        ingest_document_task.apply, args=[str(org_id), str(eq_id), str(sample_pdf)]
    )
    doc_id = uuid.UUID(result.get())

    async with session_for_org(org_id) as s:
        doc = await s.get(Document, doc_id)
        assert doc is not None
