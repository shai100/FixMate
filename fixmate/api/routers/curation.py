import uuid

from fastapi import APIRouter, Depends, HTTPException

from fixmate.api.deps import AuthContext, require_role
from fixmate.api.schemas import ApproveRequest, ResolveRequest, ReviewItemOut
from fixmate.curation.service import (
    FixNotFound,
    IllegalTransition,
    approve,
    flag_unsafe,
    reject,
    retire,
    review_queue,
)

# All curation actions require a reviewer role (FR-14). The dependency rejects
# technicians with 403 before any handler logic runs; the service layer guards
# again (defense in depth).
reviewer = require_role("curator", "admin")

queue_router = APIRouter(prefix="/curation", tags=["curation"])
fixes_router = APIRouter(prefix="/fixes", tags=["curation"])


@queue_router.get("/queue", response_model=list[ReviewItemOut])
async def get_queue(auth: AuthContext = Depends(reviewer)) -> list[ReviewItemOut]:
    items = await review_queue(auth.org_id)
    return [
        ReviewItemOut(
            fix_id=i.fix_id,
            state=i.state,
            question=i.question,
            original_answer=i.original_answer,
            proposed_text=i.proposed_text,
            submitted_by=i.submitted_by,
            equipment_id=i.equipment_id,
            manual_chunks=i.manual_chunks,
            prescreen=i.prescreen,
            created_at=i.created_at,
        )
        for i in items
    ]


def _map_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, FixNotFound):
        return HTTPException(status_code=404, detail="fix not found")
    if isinstance(exc, IllegalTransition):
        return HTTPException(status_code=409, detail=f"illegal state transition: {exc}")
    raise exc


@fixes_router.post("/{fix_id}/approve", status_code=204)
async def approve_fix(
    fix_id: uuid.UUID,
    body: ApproveRequest | None = None,
    auth: AuthContext = Depends(reviewer),
) -> None:
    try:
        await approve(
            auth.org_id,
            fix_id,
            auth.user_id,
            auth.role,
            edited_text=body.edited_text if body else None,
        )
    except (FixNotFound, IllegalTransition) as exc:
        raise _map_errors(exc) from exc


@fixes_router.post("/{fix_id}/reject", status_code=204)
async def reject_fix(
    fix_id: uuid.UUID,
    body: ResolveRequest,
    auth: AuthContext = Depends(reviewer),
) -> None:
    try:
        await reject(auth.org_id, fix_id, auth.user_id, auth.role, body.reason)
    except (FixNotFound, IllegalTransition) as exc:
        raise _map_errors(exc) from exc


@fixes_router.post("/{fix_id}/unsafe", status_code=204)
async def unsafe_fix(
    fix_id: uuid.UUID,
    body: ResolveRequest,
    auth: AuthContext = Depends(reviewer),
) -> None:
    try:
        await flag_unsafe(auth.org_id, fix_id, auth.user_id, auth.role, body.reason)
    except (FixNotFound, IllegalTransition) as exc:
        raise _map_errors(exc) from exc


@fixes_router.post("/{fix_id}/retire", status_code=204)
async def retire_fix(
    fix_id: uuid.UUID,
    body: ResolveRequest,
    auth: AuthContext = Depends(reviewer),
) -> None:
    try:
        await retire(auth.org_id, fix_id, auth.user_id, auth.role, body.reason)
    except (FixNotFound, IllegalTransition) as exc:
        raise _map_errors(exc) from exc
