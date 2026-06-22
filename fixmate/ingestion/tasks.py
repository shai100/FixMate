"""Celery task definition that runs ingestion in a background worker.

PDF ingestion is slow (extraction, embedding, captioning), so the upload endpoint
enqueues this task instead of blocking the HTTP request. The Celery app here uses
Redis as both broker and result backend; the worker picks up the task and runs
the (synchronous) ingestion pipeline.
"""

import uuid
from pathlib import Path

from celery import Celery

from fixmate.core.settings import settings
from fixmate.ingestion.pipeline import ingest_document_sync

app = Celery("fixmate", broker=settings.redis_url, backend=settings.redis_url)


def _resolve_pdf_path(pdf_path: str) -> str:
    """Resolve the handoff path the API/CLI passed into a file the worker can read.

    The API hands off only the staged *filename* (so a containerized worker reads
    it from its own ``upload_dir`` bind mount rather than a host-absolute path).
    The CLI ``--async`` path may instead pass a real path that already exists. So:
    use the path as-is if it exists; otherwise resolve its basename under
    ``settings.upload_dir`` (the API handoff case).
    """
    if Path(pdf_path).exists():
        return pdf_path
    # Separator-agnostic basename: the API stages a bare filename, but be robust
    # to a path that used the *other* OS's separator (e.g. a Windows host API
    # handing a path to a Linux worker container) so we never glue a full path
    # onto upload_dir.
    base = pdf_path.replace("\\", "/").rsplit("/", 1)[-1]
    return str(Path(settings.upload_dir) / base)


@app.task(bind=True, name="fixmate.ingestion.ingest_document")
def ingest_document_task(
    self, org_id: str, equipment_id: str, pdf_path: str, title: str | None = None
) -> str:
    """Worker entry point: ingest a PDF and return the new document id as a string.

    Args are plain strings (UUIDs aren't JSON-serializable for the result
    backend); the id is likewise returned as a string for the same reason.

    The task is ``bind=True`` so the pipeline's progress callback can publish a
    custom ``PROGRESS`` state carrying ``{stage, percent}`` to the result backend.
    The status endpoint (``api/routers/documents.py``) reads that meta back so the
    upload UI can render a live progress bar instead of a static "Queued…" label.
    """

    def _publish(stage: str, percent: int) -> None:
        # PROGRESS is a Celery custom state: meta is stored verbatim and surfaces
        # as AsyncResult.info while the task runs. Both fields are plain JSON.
        self.update_state(state="PROGRESS", meta={"stage": stage, "percent": percent})

    # Return a str (UUID isn't JSON-serializable for the result backend).
    doc_id: uuid.UUID = ingest_document_sync(
        org_id, equipment_id, _resolve_pdf_path(pdf_path), title, progress=_publish
    )
    return str(doc_id)
