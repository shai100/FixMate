"""Manual (PDF) upload, listing, versioning, and deletion.

Uploading is asynchronous: this router validates the PDF, writes it to a temp
file, and enqueues a Celery ingestion task (``fixmate/ingestion/tasks.py``) that
does the slow work (text extraction, chunking, embedding, figure captioning).
Clients poll ``GET /documents/{task_id}`` for progress. The other endpoints
manage the resulting ``Document`` rows, whose version lineage is immutable
provenance — only the title can be edited.
"""

import uuid
from pathlib import Path

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import select

from fixmate.api.deps import AuthContext, get_current_user
from fixmate.api.schemas import DocumentOut, DocumentStatus, UpdateDocument, UploadAccepted
from fixmate.core import storage
from fixmate.core.db import session_for_org
from fixmate.core.models import AuditEvent, Document, Figure
from fixmate.core.settings import settings
from fixmate.ingestion.tasks import ingest_document_task

router = APIRouter(prefix="/documents", tags=["documents"])

# Uploads are staged to a shared directory and the Celery worker is handed only
# the staged *filename* (not an absolute path), so a worker running in a
# container resolves the same file via a bind mount of this directory — see
# settings.upload_dir. The pipeline re-uploads the original PDF to MinIO under
# the tenant prefix, so this staged file is only the enqueue handoff.
_UPLOAD_DIR = Path(settings.upload_dir)


@router.post("/upload", status_code=202, response_model=UploadAccepted)
async def upload_document(
    file: UploadFile = File(...),
    equipment_id: str = Form(...),
    title: str | None = Form(default=None),
    auth: AuthContext = Depends(get_current_user),
) -> UploadAccepted:
    """Accept a PDF upload and enqueue it for background ingestion (returns 202).

    Validates that the file is a non-empty PDF and that ``equipment_id`` is a
    UUID, stages the bytes to a temp file, then kicks off the Celery task and
    returns its id so the client can poll ``document_status``.
    """
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
    # Unique prefix avoids collisions; only the filename is passed to the worker,
    # which re-resolves it against its own upload_dir (host or container path).
    staged_name = f"{uuid.uuid4()}-{Path(name).name}"
    (_UPLOAD_DIR / staged_name).write_bytes(data)

    task = ingest_document_task.delay(
        str(auth.org_id), str(eq_id), staged_name, title or Path(name).name
    )
    return UploadAccepted(task_id=task.id, status="queued")


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    equipment_id: str | None = None,
    auth: AuthContext = Depends(get_current_user),
) -> list[DocumentOut]:
    """List manuals (newest first), optionally filtered to one equipment profile.

    Newest-first ordering surfaces the live revision (``superseded_by is null``)
    above its superseded ancestors in the admin console.
    """
    # Version list for the admin console (FR-9): newest first so the live
    # revision (superseded_by is null) surfaces above its superseded ancestors.
    # `equipment_id` scopes the list to one profile's attached manuals.
    eq_id = None
    if equipment_id is not None:
        try:
            eq_id = uuid.UUID(equipment_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="equipment_id must be a UUID") from exc
    async with session_for_org(auth.org_id) as s:
        stmt = select(Document).order_by(Document.created_at.desc())
        if eq_id is not None:
            stmt = stmt.where(Document.equipment_id == eq_id)
        rows = (await s.execute(stmt)).scalars().all()
        return [
            DocumentOut(
                id=d.id,
                equipment_id=d.equipment_id,
                title=d.title,
                version=d.version,
                superseded_by=d.superseded_by,
                created_at=d.created_at,
            )
            for d in rows
        ]


@router.patch("/{document_id}", response_model=DocumentOut)
async def update_document(
    document_id: uuid.UUID,
    body: UpdateDocument,
    auth: AuthContext = Depends(get_current_user),
) -> DocumentOut:
    """Rename a manual (the only editable field) and record an audit event."""
    # Set details (FR-8): the only mutable field on a document is its title;
    # version lineage and storage key are immutable provenance.
    async with session_for_org(auth.org_id) as s:
        doc = await s.get(Document, document_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="document not found")
        if body.title is not None:
            new_title = body.title.strip()
            if not new_title:
                raise HTTPException(status_code=422, detail="title must not be empty")
            before = doc.title
            doc.title = new_title
            s.add(
                AuditEvent(
                    organization_id=auth.org_id,
                    actor_id=auth.user_id,
                    entity_type="document",
                    entity_id=doc.id,
                    action="edit",
                    before={"title": before},
                    after={"title": new_title},
                )
            )
        await s.commit()
        return DocumentOut(
            id=doc.id,
            equipment_id=doc.equipment_id,
            title=doc.title,
            version=doc.version,
            superseded_by=doc.superseded_by,
            created_at=doc.created_at,
        )


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    """Delete a manual, its indexed chunks/figures, and its stored files (returns 204).

    DB rows cascade-delete inside the transaction (dropping the manual from
    retrieval immediately); object-storage cleanup runs *after* the commit and is
    best-effort so a storage hiccup can't leave a half-deleted index.
    """
    # Remove a manual and everything indexed from it. Chunks and figures cascade
    # on the document FK (ondelete=CASCADE), so deleting the row drops it from
    # retrieval immediately — the index is the single source of truth (spec §2.4).
    async with session_for_org(auth.org_id) as s:
        doc = await s.get(Document, document_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="document not found")
        figure_keys = (
            (
                await s.execute(
                    select(Figure.storage_key).where(Figure.document_id == doc.id)
                )
            )
            .scalars()
            .all()
        )
        storage_key = doc.storage_key
        s.add(
            AuditEvent(
                organization_id=auth.org_id,
                actor_id=auth.user_id,
                entity_type="document",
                entity_id=doc.id,
                action="delete",
                before={"title": doc.title, "version": doc.version},
                after=None,
            )
        )
        await s.delete(doc)
        await s.commit()
    # Storage cleanup is best-effort and runs after the DB commit so a storage
    # hiccup can never leave a half-deleted index behind.
    for key in [storage_key, *figure_keys]:
        storage.delete_object(key)


@router.get("/{document_id}/download")
async def download_document(
    document_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
) -> Response:
    """Stream the original manual PDF back to the client as a file download.

    The object store bucket is private, so rather than expose it the API fetches
    the bytes itself (under the caller's tenant scope via ``session_for_org``) and
    returns them with a ``Content-Disposition: attachment`` header so the browser
    saves the file. The PDF is looked up by document id, not by raw storage key,
    so a caller can only ever download a manual their own org owns.
    """
    async with session_for_org(auth.org_id) as s:
        doc = await s.get(Document, document_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="document not found")
        title = doc.title
        storage_key = doc.storage_key
    try:
        data = storage.get_object(storage_key)
    except ClientError as exc:
        raise HTTPException(status_code=404, detail="stored file is unavailable") from exc

    filename = title if title.lower().endswith(".pdf") else f"{title}.pdf"
    # RFC 6266: quote the filename so titles with spaces survive the round-trip.
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{task_id}", response_model=DocumentStatus)
async def document_status(
    task_id: str,
    auth: AuthContext = Depends(get_current_user),
) -> DocumentStatus:
    """Report ingestion progress for an upload task.

    Reads the Celery task state; on success returns the new document id, while a
    running task is reported as ``processing`` with the live ``stage``/``percent``
    the worker published, otherwise the lowercased task state ("pending",
    "failure", ...).
    """
    # Ingestion status (FR-8) is read from the Celery result: the task returns
    # the new document id on success. PENDING covers both "queued" and "unknown
    # id" — acceptable for the MVP handoff.
    result = ingest_document_task.AsyncResult(task_id)
    state = result.state
    if state == "SUCCESS":
        return DocumentStatus(
            task_id=task_id, status="ingested", percent=100, document_id=uuid.UUID(result.result)
        )
    if state == "PROGRESS":
        # Custom state published by the worker: info is the {stage, percent} meta.
        info = result.info if isinstance(result.info, dict) else {}
        return DocumentStatus(
            task_id=task_id,
            status="processing",
            stage=info.get("stage"),
            percent=info.get("percent"),
        )
    return DocumentStatus(task_id=task_id, status=state.lower())
