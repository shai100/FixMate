import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from fixmate.core.models import Document, EquipmentProfile, Organization
from fixmate.core.settings import settings


async def get_or_create_org(name: str) -> uuid.UUID:
    # Org creation is a bootstrap operation outside any tenant context, so it
    # runs on the owner connection (not fixmate_app) — mirrors tests/conftest.py.
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            existing = await conn.scalar(
                select(Organization.id).where(Organization.name == name)
            )
            if existing:
                return existing
            return await conn.scalar(
                Organization.__table__.insert().values(name=name).returning(Organization.id)
            )
    finally:
        await engine.dispose()


async def get_or_create_equipment(
    session: AsyncSession, org_id: uuid.UUID, name: str
) -> uuid.UUID:
    eid = await session.scalar(
        select(EquipmentProfile.id).where(
            EquipmentProfile.organization_id == org_id, EquipmentProfile.name == name
        )
    )
    if eid:
        return eid
    eq = EquipmentProfile(organization_id=org_id, name=name)
    session.add(eq)
    await session.flush()
    return eq.id


async def latest_document(
    session: AsyncSession, org_id: uuid.UUID, equipment_id: uuid.UUID, title: str
) -> Document | None:
    return await session.scalar(
        select(Document)
        .where(
            Document.organization_id == org_id,
            Document.equipment_id == equipment_id,
            Document.title == title,
        )
        .order_by(Document.version.desc())
        .limit(1)
    )
