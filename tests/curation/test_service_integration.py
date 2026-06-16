import pytest
from sqlalchemy import select

from fixmate.core.db import session_for_org
from fixmate.core.models import AuditEvent, Chunk, Fix, User
from fixmate.curation.service import (
    IllegalTransition,
    NotAuthorized,
    approve,
    create_fix,
    flag_unsafe,
    reject,
    retire,
    review_queue,
)
from fixmate.retrieval.service import search

pytestmark = pytest.mark.integration


async def test_review_queue_returns_context_and_prescreen(curation_world):
    w = curation_world
    items = await review_queue(w.org_id)

    assert len(items) == 1
    item = items[0]
    assert item.fix_id == w.fix_id
    assert item.question == "How do I clear error E47?"
    assert item.original_answer is not None
    assert item.proposed_text.startswith("Error E47")
    assert any("E47" in c["text"] for c in item.manual_chunks)
    assert item.prescreen is not None

    # Pre-screen is persisted, so a second fetch does not regenerate it.
    async with session_for_org(w.org_id) as s:
        fix = await s.get(Fix, w.fix_id)
        assert fix.ai_prescreen_report is not None


async def test_approve_indexes_field_fix_and_audits(curation_world):
    w = curation_world
    await approve(w.org_id, w.fix_id, w.curator_id, role="curator")

    async with session_for_org(w.org_id) as s:
        fix = await s.get(Fix, w.fix_id)
        assert fix.state == "approved"
        assert fix.reviewed_by == w.curator_id
        assert fix.approved_at is not None

        field_chunks = (
            await s.execute(select(Chunk).where(Chunk.fix_id == w.fix_id))
        ).scalars().all()
        assert field_chunks
        assert all(c.source_type == "field_fix" for c in field_chunks)

        audit = (
            await s.execute(
                select(AuditEvent).where(
                    AuditEvent.entity_id == w.fix_id, AuditEvent.action == "approve"
                )
            )
        ).scalars().one()
        assert audit.before["state"] == "pending_review"
        assert audit.after["state"] == "approved"


async def test_edit_and_approve_persists_curator_text(curation_world):
    w = curation_world
    edited = "Replace concentrate valve cartridge AB-1234 to clear error E47."
    await approve(w.org_id, w.fix_id, w.curator_id, role="curator", edited_text=edited)

    async with session_for_org(w.org_id) as s:
        fix = await s.get(Fix, w.fix_id)
        assert fix.proposed_text == edited
        chunk = (
            await s.execute(select(Chunk).where(Chunk.fix_id == w.fix_id))
        ).scalars().first()
        assert "AB-1234" in chunk.content


async def test_admin_can_approve_fix_they_created(curation_world):
    """An admin who opens a fix can approve it: curation authority is a role
    check, never a self-approval block (the reviewer and submitter may be the
    same person). Locks in issue #2."""
    w = curation_world
    async with session_for_org(w.org_id) as s:
        admin = User(organization_id=w.org_id, name="Andy Admin", role="admin")
        s.add(admin)
        await s.flush()
        admin_id = admin.id
        await s.commit()

    fix_id = await create_fix(
        w.org_id,
        w.equipment_id,
        admin_id,
        role="admin",
        proposed_text="Replace the inlet gasket and re-seat the cover to clear the leak.",
        question="Cover leaks after service",
    )

    # Same admin both submitted and approves — no block.
    await approve(w.org_id, fix_id, admin_id, role="admin")

    async with session_for_org(w.org_id) as s:
        fix = await s.get(Fix, fix_id)
        assert fix.state == "approved"
        assert fix.submitted_by == admin_id
        assert fix.reviewed_by == admin_id


async def test_tech_cannot_approve(curation_world):
    w = curation_world
    with pytest.raises(NotAuthorized):
        await approve(w.org_id, w.fix_id, w.tech_id, role="tech")


async def test_cannot_approve_already_rejected(curation_world):
    w = curation_world
    await reject(w.org_id, w.fix_id, w.curator_id, role="curator", reason="duplicate")
    with pytest.raises(IllegalTransition):
        await approve(w.org_id, w.fix_id, w.curator_id, role="curator")


async def test_reject_records_reason(curation_world):
    w = curation_world
    await reject(w.org_id, w.fix_id, w.curator_id, role="curator", reason="contradicts manual")
    async with session_for_org(w.org_id) as s:
        fix = await s.get(Fix, w.fix_id)
        assert fix.state == "rejected"
        assert fix.review_notes == "contradicts manual"
        # A rejected fix is never indexed.
        chunks = (
            await s.execute(select(Chunk).where(Chunk.fix_id == w.fix_id))
        ).scalars().all()
        assert chunks == []


async def test_flag_unsafe_records_reason(curation_world):
    w = curation_world
    await flag_unsafe(w.org_id, w.fix_id, w.curator_id, role="curator", reason="bypasses interlock")
    async with session_for_org(w.org_id) as s:
        fix = await s.get(Fix, w.fix_id)
        assert fix.state == "unsafe"
        assert fix.review_notes == "bypasses interlock"


async def test_moat_approved_fix_outranks_manual_then_disappears_on_retire(curation_world):
    """The moat (spec §2.4): approve → field fix outranks manual on its symptom;
    retire → it vanishes from retrieval immediately."""
    w = curation_world
    await approve(w.org_id, w.fix_id, w.curator_id, role="curator")

    results = await search(w.org_id, w.equipment_id, "error E47 concentrate valve")
    assert results
    assert results[0].source_type == "field_fix"
    assert results[0].fix_id == w.fix_id

    await retire(w.org_id, w.fix_id, w.curator_id, role="curator", reason="superseded")

    async with session_for_org(w.org_id) as s:
        fix = await s.get(Fix, w.fix_id)
        assert fix.state == "retired"
        chunks = (
            await s.execute(select(Chunk).where(Chunk.fix_id == w.fix_id))
        ).scalars().all()
        assert chunks == []

    after = await search(w.org_id, w.equipment_id, "error E47 concentrate valve")
    assert all(r.source_type != "field_fix" for r in after)
