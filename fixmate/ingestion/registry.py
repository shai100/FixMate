"""Lookup/bootstrap helpers used by ingestion, CLIs, and seeding.

These functions answer "find this org/equipment, creating it if needed" and
"what's the latest version of this document?". Org creation is special: it
happens *before* any tenant exists, so — unlike normal app code — it connects on
the owner role (``database_url``) rather than the RLS-restricted app role. The
equipment/document helpers run inside a caller-provided tenant session.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from fixmate.core.models import Document, EquipmentProfile, Organization
from fixmate.core.settings import settings


async def get_or_create_org(name: str) -> uuid.UUID:
    """Return the id of the org with this name, creating it if absent (bootstrap)."""
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
    """Return the id of the named equipment profile in this org, creating if absent."""
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
    """Return the highest-version document for this (org, equipment, title), or None.

    Used during ingestion to decide the next version number and which prior
    document to mark superseded.
    """
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
