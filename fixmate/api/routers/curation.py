import uuid

from fastapi import APIRouter, Depends, HTTPException

from fixmate.api.deps import AuthContext, require_role
from fixmate.api.schemas import (
    ApproveRequest,
    CreateFixRequest,
    FixSummaryOut,
    ResolveRequest,
    ReviewItemOut,
    UpdateFixRequest,
)
from fixmate.curation.service import (
    FixNotFound,
    IllegalTransition,
    approve,
    create_fix,
    delete_fix,
    flag_unsafe,
    list_fixes,
    reject,
    retire,
    review_queue,
    update_fix,
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


@queue_router.get("/fixes", response_model=list[FixSummaryOut])
async def get_all_fixes(
    state: str | None = None,
    auth: AuthContext = Depends(reviewer),
) -> list[FixSummaryOut]:
    states = tuple(state.split(",")) if state else None
    items = await list_fixes(auth.org_id, states)
    return [
        FixSummaryOut(
            fix_id=i.fix_id,
            state=i.state,
            question=i.question,
            proposed_text=i.proposed_text,
            equipment_id=i.equipment_id,
            submitted_by=i.submitted_by,
            submitted_by_name=i.submitted_by_name,
            reviewed_by=i.reviewed_by,
            reviewed_by_name=i.reviewed_by_name,
            review_notes=i.review_notes,
            approved_at=i.approved_at,
            created_at=i.created_at,
            updated_at=i.updated_at,
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


@fixes_router.post("", status_code=201)
async def create_new_fix(
    body: CreateFixRequest,
    auth: AuthContext = Depends(reviewer),
) -> dict:
    try:
        fix_id = await create_fix(
            auth.org_id,
            body.equipment_id,
            auth.user_id,
            auth.role,
            body.proposed_text,
            question=body.question,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"fix_id": str(fix_id)}


@fixes_router.patch("/{fix_id}", status_code=204)
async def edit_fix(
    fix_id: uuid.UUID,
    body: UpdateFixRequest,
    auth: AuthContext = Depends(reviewer),
) -> None:
    try:
        await update_fix(
            auth.org_id,
            fix_id,
            auth.user_id,
            auth.role,
            proposed_text=body.proposed_text,
            question=body.question,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FixNotFound as exc:
        raise _map_errors(exc) from exc


@fixes_router.delete("/{fix_id}", status_code=204)
async def remove_fix(
    fix_id: uuid.UUID,
    auth: AuthContext = Depends(reviewer),
) -> None:
    try:
        await delete_fix(auth.org_id, fix_id, auth.user_id, auth.role)
    except FixNotFound as exc:
        raise _map_errors(exc) from exc
