import pytest
from sqlalchemy import select

from fixmate.core import storage
from fixmate.core.db import session_for_org
from fixmate.core.models import Chunk, Document, EquipmentProfile, Figure
from fixmate.ingestion.pipeline import ingest_document

pytestmark = pytest.mark.integration


async def _make_equipment(org_id):
    async with session_for_org(org_id) as s:
        eq = EquipmentProfile(organization_id=org_id, name="Pump X")
        s.add(eq)
        await s.commit()
        return eq.id


async def test_ingest_creates_document_chunks_and_figure(two_orgs, sample_pdf):
    org_id, _ = two_orgs
    eq_id = await _make_equipment(org_id)

    doc_id = await ingest_document(org_id, eq_id, sample_pdf)

    async with session_for_org(org_id) as s:
        doc = (await s.execute(select(Document).where(Document.id == doc_id))).scalar_one()
        assert doc.version == 1

        chunks = (
            await s.execute(select(Chunk).where(Chunk.document_id == doc_id))
        ).scalars().all()
        assert len(chunks) >= 1
        assert all(c.source_type == "manual" for c in chunks)
        assert all(len(c.embedding) == 1024 for c in chunks)

        figures = (
            await s.execute(select(Figure).where(Figure.document_id == doc_id))
        ).scalars().all()
        assert len(figures) == 1
        assert figures[0].caption
        assert storage.object_exists(figures[0].storage_key)


async def test_reingest_bumps_version_and_supersedes(two_orgs, sample_pdf):
    org_id, _ = two_orgs
    eq_id = await _make_equipment(org_id)

    v1_id = await ingest_document(org_id, eq_id, sample_pdf)
    v2_id = await ingest_document(org_id, eq_id, sample_pdf)

    async with session_for_org(org_id) as s:
        v1 = (await s.execute(select(Document).where(Document.id == v1_id))).scalar_one()
        v2 = (await s.execute(select(Document).where(Document.id == v2_id))).scalar_one()
        assert v2.version == 2
        assert v1.superseded_by == v2_id
