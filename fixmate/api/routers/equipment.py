"""CRUD for equipment profiles (the machines technicians troubleshoot).

Every mutating action also writes an ``AuditEvent`` so changes are traceable
(CLAUDE.md §8.2). Deleting a profile cascades to all of its manuals, chunks,
figures, and fixes — removing them from retrieval in one transaction.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from fixmate.api.deps import AuthContext, get_current_user
from fixmate.api.schemas import CreateEquipment, EquipmentOut, UpdateEquipment
from fixmate.core.db import session_for_org
from fixmate.core.models import AuditEvent, EquipmentProfile

router = APIRouter(prefix="/equipment", tags=["equipment"])


def _equipment_out(e: EquipmentProfile) -> EquipmentOut:
    """Convert an ``EquipmentProfile`` ORM row into its API response model."""
    return EquipmentOut(
        id=e.id,
        name=e.name,
        manufacturer=e.manufacturer,
        model=e.model,
        created_at=e.created_at,
    )


@router.post("", status_code=201, response_model=EquipmentOut)
async def create_equipment(
    body: CreateEquipment,
    auth: AuthContext = Depends(get_current_user),
) -> EquipmentOut:
    """Register a new equipment profile for the caller's tenant (returns 201)."""
    async with session_for_org(auth.org_id) as s:
        eq = EquipmentProfile(
            organization_id=auth.org_id,
            name=body.name,
            manufacturer=body.manufacturer,
            model=body.model,
        )
        s.add(eq)
        await s.commit()
        return _equipment_out(eq)


@router.get("", response_model=list[EquipmentOut])
async def list_equipment(
    auth: AuthContext = Depends(get_current_user),
) -> list[EquipmentOut]:
    """List the tenant's equipment profiles, oldest first."""
    async with session_for_org(auth.org_id) as s:
        rows = (
            (await s.execute(select(EquipmentProfile).order_by(EquipmentProfile.created_at)))
            .scalars()
            .all()
        )
        return [_equipment_out(e) for e in rows]


@router.get("/{equipment_id}", response_model=EquipmentOut)
async def get_equipment(
    equipment_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
) -> EquipmentOut:
    """Fetch one equipment profile by id (404 if not visible to this tenant)."""
    async with session_for_org(auth.org_id) as s:
        eq = await s.get(EquipmentProfile, equipment_id)
        if eq is None:
            raise HTTPException(status_code=404, detail="equipment not found")
        return _equipment_out(eq)


@router.patch("/{equipment_id}", response_model=EquipmentOut)
async def update_equipment(
    equipment_id: uuid.UUID,
    body: UpdateEquipment,
    auth: AuthContext = Depends(get_current_user),
) -> EquipmentOut:
    """Partially update an equipment profile and record an audit event.

    Only the fields present in the body are changed; blank manufacturer/model are
    normalized to NULL. Captures before/after snapshots for the audit trail.
    """
    async with session_for_org(auth.org_id) as s:
        eq = await s.get(EquipmentProfile, equipment_id)
        if eq is None:
            raise HTTPException(status_code=404, detail="equipment not found")
        before = {"name": eq.name, "manufacturer": eq.manufacturer, "model": eq.model}
        if body.name is not None:
            name = body.name.strip()
            if not name:
                raise HTTPException(status_code=422, detail="name must not be empty")
            eq.name = name
        if body.manufacturer is not None:
            eq.manufacturer = body.manufacturer.strip() or None
        if body.model is not None:
            eq.model = body.model.strip() or None
        s.add(
            AuditEvent(
                organization_id=auth.org_id,
                actor_id=auth.user_id,
                entity_type="equipment",
                entity_id=eq.id,
                action="edit",
                before=before,
                after={"name": eq.name, "manufacturer": eq.manufacturer, "model": eq.model},
            )
        )
        await s.commit()
        return _equipment_out(eq)


@router.delete("/{equipment_id}", status_code=204)
async def delete_equipment(
    equipment_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
) -> None:
    """Delete an equipment profile and everything attached to it (returns 204).

    The cascade (see note below) removes all related manuals/chunks/fixes from
    retrieval atomically; an audit event records the deletion first.
    """
    # Deleting a profile cascades to its documents, chunks, figures and fixes
    # (all carry an ondelete=CASCADE FK to equipment), removing everything from
    # retrieval in one transaction — the index is the single source of truth.
    async with session_for_org(auth.org_id) as s:
        eq = await s.get(EquipmentProfile, equipment_id)
        if eq is None:
            raise HTTPException(status_code=404, detail="equipment not found")
        s.add(
            AuditEvent(
                organization_id=auth.org_id,
                actor_id=auth.user_id,
                entity_type="equipment",
                entity_id=eq.id,
                action="delete",
                before={"name": eq.name, "manufacturer": eq.manufacturer, "model": eq.model},
                after=None,
            )
        )
        await s.delete(eq)
        await s.commit()
