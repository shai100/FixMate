import pytest
from sqlalchemy import select

from fixmate.core.db import session_for_org
from fixmate.core.models import EquipmentProfile


@pytest.mark.asyncio
async def test_rls_blocks_cross_tenant_reads(two_orgs):
    org_a, org_b = two_orgs
    async with session_for_org(org_a) as s:
        s.add(EquipmentProfile(organization_id=org_a, name="Pump X"))
        await s.commit()
    async with session_for_org(org_b) as s:
        rows = (await s.execute(select(EquipmentProfile))).scalars().all()
        assert rows == []  # org_b must not see org_a's data


@pytest.mark.asyncio
async def test_rls_blocks_cross_tenant_insert(two_orgs):
    org_a, org_b = two_orgs
    async with session_for_org(org_b) as s:
        s.add(EquipmentProfile(organization_id=org_a, name="Sneaky"))
        with pytest.raises(Exception):  # RLS WITH CHECK violation
            await s.commit()


@pytest.mark.asyncio
async def test_same_org_reads_back_its_own_rows(two_orgs):
    org_a, _ = two_orgs
    async with session_for_org(org_a) as s:
        s.add(EquipmentProfile(organization_id=org_a, name="Pump Y"))
        await s.commit()
    async with session_for_org(org_a) as s:
        names = (await s.execute(select(EquipmentProfile.name))).scalars().all()
        assert "Pump Y" in names
