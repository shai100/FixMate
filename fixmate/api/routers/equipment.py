from fastapi import APIRouter, Depends
from sqlalchemy import select

from fixmate.api.deps import AuthContext, get_current_user
from fixmate.api.schemas import CreateEquipment, EquipmentOut
from fixmate.core.db import session_for_org
from fixmate.core.models import EquipmentProfile

router = APIRouter(prefix="/equipment", tags=["equipment"])


@router.post("", status_code=201, response_model=EquipmentOut)
async def create_equipment(
    body: CreateEquipment,
    auth: AuthContext = Depends(get_current_user),
) -> EquipmentOut:
    async with session_for_org(auth.org_id) as s:
        eq = EquipmentProfile(
            organization_id=auth.org_id,
            name=body.name,
            manufacturer=body.manufacturer,
            model=body.model,
        )
        s.add(eq)
        await s.commit()
        return EquipmentOut(
            id=eq.id,
            name=eq.name,
            manufacturer=eq.manufacturer,
            model=eq.model,
            created_at=eq.created_at,
        )


@router.get("", response_model=list[EquipmentOut])
async def list_equipment(
    auth: AuthContext = Depends(get_current_user),
) -> list[EquipmentOut]:
    async with session_for_org(auth.org_id) as s:
        rows = (
            (await s.execute(select(EquipmentProfile).order_by(EquipmentProfile.created_at)))
            .scalars()
            .all()
        )
        return [
            EquipmentOut(
                id=e.id,
                name=e.name,
                manufacturer=e.manufacturer,
                model=e.model,
                created_at=e.created_at,
            )
            for e in rows
        ]
