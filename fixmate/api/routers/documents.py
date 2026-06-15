import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from fixmate.api.deps import AuthContext, get_current_user
from fixmate.api.schemas import DocumentStatus, UploadAccepted
from fixmate.ingestion.tasks import ingest_document_task

router = APIRouter(prefix="/documents", tags=["documents"])

# Uploads are handed to the Celery worker as a filesystem path (worker + API
# share the host in the local profile). The pipeline re-uploads the original PDF
# to MinIO under the tenant prefix, so this temp file is only the enqueue handoff.
_UPLOAD_DIR = Path(tempfile.gettempdir()) / "fixmate-uploads"


@router.post("/upload", status_code=202, response_model=UploadAccepted)
async def upload_document(
    file: UploadFile = File(...),
    equipment_id: str = Form(...),
    title: str | None = Form(default=None),
    auth: AuthContext = Depends(get_current_user),
) -> UploadAccepted:
    # Boundary validation (CLAUDE.md §4.2): reject anything that is not a PDF.
    is_pdf = (file.content_type == "application/pdf") or (file.filename or "").lower().endswith(
        ".pdf"
    )
    if not is_pdf:
        raise HTTPException(status_code=400, detail="only application/pdf uploads are accepted")
    try:
        eq_id = uuid.UUID(equipment_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="equipment_id must be a UUID") from exc

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="uploaded file is empty")

    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = file.filename or f"{uuid.uuid4()}.pdf"
    dest = _UPLOAD_DIR / f"{uuid.uuid4()}-{Path(name).name}"
    dest.write_bytes(data)

    task = ingest_document_task.delay(
        str(auth.org_id), str(eq_id), str(dest), title or Path(name).name
    )
    return UploadAccepted(task_id=task.id, status="queued")


@router.get("/{task_id}", response_model=DocumentStatus)
async def document_status(
    task_id: str,
    auth: AuthContext = Depends(get_current_user),
) -> DocumentStatus:
    # Ingestion status (FR-8) is read from the Celery result: the task returns
    # the new document id on success. PENDING covers both "queued" and "unknown
    # id" — acceptable for the MVP handoff.
    result = ingest_document_task.AsyncResult(task_id)
    state = result.state
    if state == "SUCCESS":
        return DocumentStatus(
            task_id=task_id, status="ingested", document_id=uuid.UUID(result.result)
        )
    return DocumentStatus(task_id=task_id, status=state.lower())
