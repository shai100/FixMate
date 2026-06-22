"""The document-ingestion pipeline — turns an uploaded PDF into searchable data.

This is the orchestration layer that ties together the smaller ingestion pieces:
extract the page text (``pdf.py``) -> split it into overlapping chunks
(``chunking.py``) -> embed each chunk (``llm/embeddings.py``) -> extract and
caption figures (``pdf.py`` + ``figures.py``) -> write everything to the database
and object storage, handling version supersession. After this runs, the manual is
fully retrievable. ``ingest_document`` is the async core; ``ingest_document_sync``
wraps it for the Celery worker.
"""

import asyncio
import uuid
from collections.abc import Callable
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

# Max figure-captioning vision calls in flight at once. Tuned to overlap network
# latency without overwhelming the provider's per-request concurrency limits.
_CAPTION_CONCURRENCY = 8

# A progress callback reports ``(stage_label, overall_percent)`` so the upload UI
# can render a real progress bar instead of a static "Queued…" message. The
# percent budget below splits the pipeline by where wall-clock time actually goes
# on the local CPU profile: embedding dominates, so it owns the widest band.
ProgressFn = Callable[[str, int], None]
_PCT_EXTRACTED = 8  # text + figures pulled from the PDF
_PCT_EMBED_START = 10  # embedding spans 10..70 (the bottleneck, spec §8.3)
_PCT_EMBED_END = 70
_PCT_CAPTION_END = 88  # figure captioning spans 70..88
_PCT_STORED = 100  # rows + objects written


async def ingest_document(
    org_id: uuid.UUID,
    equipment_id: uuid.UUID,
    pdf_path: str | Path,
    title: str | None = None,
    provider: LLMProvider | None = None,
    progress: ProgressFn | None = None,
) -> uuid.UUID:
    """Ingest one PDF manual for a tenant and return the new document's id.

    Runs the full pipeline (extract -> chunk -> embed -> caption figures -> store)
    and writes a ``Document`` plus its ``Chunk`` and ``Figure`` rows in a single
    transaction. Document identity is ``(equipment_id, title)``: re-ingesting the
    same title creates a *new version* and marks the previous one superseded, so
    answers always cite the current revision (FR-9 versioning).

    Args:
        org_id / equipment_id: Tenant and equipment the manual belongs to.
        pdf_path: Path to the PDF on disk.
        title: Display title; defaults to the file name. Drives version lineage.
        provider: LLM backend for figure captioning; defaults to configured one.
        progress: Optional ``(stage_label, overall_percent)`` callback used to
            drive the upload progress bar. Each call is mapped to a Celery task
            state update by the worker (``tasks.py``).
    """
    org_id = uuid.UUID(str(org_id))
    equipment_id = uuid.UUID(str(equipment_id))
    pdf_path = Path(pdf_path)
    title = title or pdf_path.name
    provider = provider or get_provider()

    def _report(stage: str, percent: int) -> None:
        if progress is not None:
            progress(stage, percent)

    _report("Reading PDF", 2)
    pdf_bytes = pdf_path.read_bytes()
    pages = extract_pages(pdf_path)
    text_chunks = chunk_pages(pages)
    figures = extract_figures(pdf_path)
    _report("Extracted text and figures", _PCT_EXTRACTED)

    # Map embedding progress (done/total chunks) onto the 10..70 percent band.
    def _embed_progress(done: int, total: int) -> None:
        span = _PCT_EMBED_END - _PCT_EMBED_START
        pct = _PCT_EMBED_START + int(span * done / total) if total else _PCT_EMBED_END
        _report(f"Embedding chunks ({done}/{total})", pct)

    embeddings = (
        await embed([c.text for c in text_chunks], on_progress=_embed_progress)
        if text_chunks
        else []
    )
    _report("Embedded chunks", _PCT_EMBED_END)

    doc_id = uuid.uuid4()
    # Caption figures concurrently. Each caption is an independent LLM vision call
    # (a network round-trip on the Anthropic backend); running them serially made
    # ingestion time scale linearly with the figure count and was the main cause
    # of long "Queued for ingestion…" waits. A bounded semaphore overlaps the
    # round-trips while capping in-flight requests so a figure-heavy manual can't
    # open hundreds of connections at once and trip provider rate limits.
    sem = asyncio.Semaphore(_CAPTION_CONCURRENCY)
    captioned = 0
    total_figs = len(figures)

    async def _caption(fig):
        nonlocal captioned
        async with sem:
            row = await caption_and_store(provider, fig, org_id, doc_id, title)
        captioned += 1
        span = _PCT_CAPTION_END - _PCT_EMBED_END
        pct = _PCT_EMBED_END + int(span * captioned / total_figs)
        _report(f"Captioning figures ({captioned}/{total_figs})", pct)
        return row

    figure_rows = await asyncio.gather(*(_caption(fig) for fig in figures))
    _report("Saving to index", _PCT_CAPTION_END)

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

    _report("Ingestion complete", _PCT_STORED)
    return doc_id


def ingest_document_sync(
    org_id: uuid.UUID,
    equipment_id: uuid.UUID,
    pdf_path: str | Path,
    title: str | None = None,
    progress: ProgressFn | None = None,
) -> uuid.UUID:
    """Blocking wrapper around ``ingest_document`` for the Celery worker.

    ``progress`` is forwarded so the worker can publish stage/percent updates to
    the Celery result backend as ingestion advances.
    """
    # Sync entry for the Celery task (workers are not async). asyncio.run gives
    # each task its own event loop, matching the NullPool engine assumption.
    return asyncio.run(
        ingest_document(org_id, equipment_id, pdf_path, title, progress=progress)
    )
