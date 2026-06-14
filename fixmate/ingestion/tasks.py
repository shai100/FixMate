import uuid

from celery import Celery

from fixmate.core.settings import settings
from fixmate.ingestion.pipeline import ingest_document_sync

app = Celery("fixmate", broker=settings.redis_url, backend=settings.redis_url)


@app.task(name="fixmate.ingestion.ingest_document")
def ingest_document_task(
    org_id: str, equipment_id: str, pdf_path: str, title: str | None = None
) -> str:
    # Return a str (UUID isn't JSON-serializable for the result backend).
    doc_id: uuid.UUID = ingest_document_sync(org_id, equipment_id, pdf_path, title)
    return str(doc_id)
