import asyncio
import uuid
from pathlib import Path

from fixmate.core import storage
from fixmate.core.db import session_for_org
from fixmate.core.models import Chunk, Document, Figure
from fixmate.ingestion import registry
from fixmate.ingestion.chunking import chunk_pages
from fixmate.ingestion.figures import caption_and_store
from fixmate.ingestion.pdf import extract_figures, extract_pages
from fixmate.llm.base import LLMProvider
from fixmate.llm.embeddings import embed
from fixmate.llm.factory import get_provider


async def ingest_document(
    org_id: uuid.UUID,
    equipment_id: uuid.UUID,
    pdf_path: str | Path,
    title: str | None = None,
    provider: LLMProvider | None = None,
) -> uuid.UUID:
    """Parse → chunk → embed → store a manual for one tenant.

    Document identity is (equipment_id, title): re-ingesting the same title
    creates a new version and supersedes the prior one (FR-9 versioning).
    """
    org_id = uuid.UUID(str(org_id))
    equipment_id = uuid.UUID(str(equipment_id))
    pdf_path = Path(pdf_path)
    title = title or pdf_path.name
    provider = provider or get_provider()

    pdf_bytes = pdf_path.read_bytes()
    pages = extract_pages(pdf_path)
    text_chunks = chunk_pages(pages)
    figures = extract_figures(pdf_path)

    embeddings = await embed([c.text for c in text_chunks]) if text_chunks else []

    doc_id = uuid.uuid4()
    figure_rows = [
        await caption_and_store(provider, fig, org_id, doc_id, title) for fig in figures
    ]

    async with session_for_org(org_id) as s:
        prev = await registry.latest_document(s, org_id, equipment_id, title)
        version = prev.version + 1 if prev else 1

        storage_key = storage.put_object(
            org_id, f"documents/{doc_id}/{pdf_path.name}", pdf_bytes, "application/pdf"
        )
        doc = Document(
            id=doc_id,
            organization_id=org_id,
            equipment_id=equipment_id,
            title=title,
            version=version,
            storage_key=storage_key,
        )
        s.add(doc)
        await s.flush()

        if prev:
            prev.superseded_by = doc_id

        for chunk, vector in zip(text_chunks, embeddings):
            s.add(
                Chunk(
                    organization_id=org_id,
                    document_id=doc_id,
                    source_type="manual",
                    content=chunk.text,
                    page=chunk.page,
                    embedding=vector,
                )
            )
        for fr in figure_rows:
            s.add(
                Figure(
                    organization_id=org_id,
                    document_id=doc_id,
                    page=fr["page"],
                    caption=fr["caption"],
                    storage_key=fr["storage_key"],
                    bbox=fr["bbox"],
                )
            )
        await s.commit()

    return doc_id


def ingest_document_sync(
    org_id: uuid.UUID,
    equipment_id: uuid.UUID,
    pdf_path: str | Path,
    title: str | None = None,
) -> uuid.UUID:
    # Sync entry for the Celery task (workers are not async). asyncio.run gives
    # each task its own event loop, matching the NullPool engine assumption.
    return asyncio.run(ingest_document(org_id, equipment_id, pdf_path, title))
