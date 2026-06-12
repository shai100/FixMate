import pytest
from sqlalchemy import text

from fixmate.core.db import session_for_org
from fixmate.core.models import Chunk, EquipmentProfile, Fix, User

EXPECTED_TABLES = {
    "organizations",
    "users",
    "equipment_profiles",
    "documents",
    "chunks",
    "figures",
    "fixes",
    "conversations",
    "messages",
    "answer_logs",
    "feedback",
    "audit_events",
}


@pytest.mark.asyncio
async def test_all_tables_exist(two_orgs):
    org_a, _ = two_orgs
    async with session_for_org(org_a) as s:
        rows = await s.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
        tables = {r[0] for r in rows}
    assert EXPECTED_TABLES <= tables


@pytest.mark.asyncio
async def test_chunk_embedding_rejects_wrong_dimension(two_orgs):
    org_a, _ = two_orgs
    async with session_for_org(org_a) as s:
        s.add(
            Chunk(
                organization_id=org_a,
                source_type="manual",
                content="dim check",
                embedding=[0.0] * 8,
            )
        )
        with pytest.raises(Exception):  # contract: vector(1024), BGE-M3
            await s.commit()


@pytest.mark.asyncio
async def test_tsv_is_generated_with_english_stemming(two_orgs):
    org_a, _ = two_orgs
    async with session_for_org(org_a) as s:
        s.add(
            Chunk(
                organization_id=org_a,
                source_type="manual",
                content="Error E47: the concentrate valves are blocked.",
                embedding=[0.0] * 1024,
            )
        )
        await s.commit()
        hits = (
            (
                await s.execute(
                    text(
                        "SELECT content FROM chunks "
                        "WHERE tsv @@ plainto_tsquery('english', 'valve')"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert any("E47" in c for c in hits)  # 'valve' must match 'valves' (stemming)


@pytest.mark.asyncio
async def test_fix_state_constraint_rejects_unknown_state(two_orgs):
    org_a, _ = two_orgs
    async with session_for_org(org_a) as s:
        user = User(organization_id=org_a, name="Tech One", role="tech")
        equipment = EquipmentProfile(organization_id=org_a, name="Pump X")
        s.add_all([user, equipment])
        await s.flush()
        s.add(
            Fix(
                organization_id=org_a,
                equipment_id=equipment.id,
                proposed_text="Just turn it off and on",
                submitted_by=user.id,
                state="bogus",
            )
        )
        with pytest.raises(Exception):
            await s.commit()


@pytest.mark.asyncio
async def test_user_role_constraint(two_orgs):
    org_a, _ = two_orgs
    async with session_for_org(org_a) as s:
        s.add(User(organization_id=org_a, name="Bad Role", role="superadmin"))
        with pytest.raises(Exception):
            await s.commit()
