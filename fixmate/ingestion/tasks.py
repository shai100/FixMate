"""Celery task definition that runs ingestion in a background worker.

PDF ingestion is slow (extraction, embedding, captioning), so the upload endpoint
enqueues this task instead of blocking the HTTP request. The Celery app here uses
Redis as both broker and result backend; the worker picks up the task and runs
the (synchronous) ingestion pipeline.
"""

import uuid

from celery import Celery

from fixmate.core.settings import settings
from fixmate.ingestion.pipeline import ingest_document_sync

app = Celery("fixmate", broker=settings.redis_url, backend=settings.redis_url)


@app.task(name="fixmate.ingestion.ingest_document")
def ingest_document_task(
    org_id: str, equipment_id: str, pdf_path: str, title: str | None = None
) -> str:
    """Worker entry point: ingest a PDF and return the new document id as a string.

    Args are plain strings (UUIDs aren't JSON-serializable for the result
    backend); the id is likewise returned as a string for the same reason.
    """
    # Return a str (UUID isn't JSON-serializable for the result backend).
    doc_id: uuid.UUID = ingest_document_sync(org_id, equipment_id, pdf_path, title)
    return str(doc_id)
