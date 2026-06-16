"""The fix-curation service — the business logic behind FixMate's moat.

This module owns the *rules* of the fix lifecycle that the API
(``api/routers/curation.py``) merely exposes. Its responsibilities:

  - Build the **review queue** with everything a curator needs, lazily running
    the AI safety pre-screen once per fix.
  - Move fixes through their lifecycle (**approve / reject / unsafe / retire**),
    enforcing legal transitions (``states.py``) and reviewer roles.
  - Keep the **search index in sync**: approving indexes a fix as ``field_fix``
    chunks (making it retrievable and able to outrank manuals); editing
    re-indexes; retiring/deleting removes the chunks. The index is the single
    source of truth (spec §2.4).
  - Write an **audit event** for every state change (spec §8.2).

Three exceptions signal the failure modes callers map to HTTP codes.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select

from fixmate.core.db import session_for_org
from fixmate.core.models import AnswerLog, AuditEvent, Chunk, Fix, User
from fixmate.curation.prescreen import prescreen
from fixmate.curation.states import can_transition
from fixmate.ingestion.chunking import chunk_pages
from fixmate.llm.base import LLMProvider
from fixmate.llm.embeddings import embed
from fixmate.retrieval.service import search

REVIEWER_ROLES = ("curator", "admin")


class FixNotFound(Exception):
    """Raised when a fix id doesn't exist (or isn't visible to this tenant)."""


class IllegalTransition(Exception):
    """The requested state change is not allowed by the fix lifecycle."""


class NotAuthorized(Exception):
    """The actor's role may not perform this curation action (FR-14)."""


@dataclass
class FixSummary:
    """A fix plus resolved submitter/reviewer names, for the admin listing."""

    fix_id: uuid.UUID
    state: str
    question: str | None
    proposed_text: str
    equipment_id: uuid.UUID
    submitted_by: uuid.UUID
    submitted_by_name: str | None
    reviewed_by: uuid.UUID | None
    reviewed_by_name: str | None
    review_notes: str | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass
class ReviewItem:
    """A fix bundled with all the evidence a curator needs to decide on it:
    the original Q&A, the proposed text, relevant manual excerpts, and the AI
    pre-screen advisory."""

    fix_id: uuid.UUID
    state: str
    question: str | None
    original_answer: str | None
    proposed_text: str
    submitted_by: uuid.UUID
    equipment_id: uuid.UUID
    manual_chunks: list[dict]
    prescreen: dict | None
    created_at: datetime


def _require_reviewer(role: str) -> None:
    """Raise ``NotAuthorized`` unless the role may curate (curator/admin)."""
    if role not in REVIEWER_ROLES:
        raise NotAuthorized(f"role {role!r} may not curate fixes; requires {REVIEWER_ROLES}")


async def _top_manual_chunks(
    org_id: uuid.UUID, equipment_id: uuid.UUID, query: str
) -> list[dict]:
    """Retrieve the most relevant *manual* excerpts for a fix, as review evidence."""
    results = await search(org_id, equipment_id, query)
    return [
        {"chunk_id": r.chunk_id, "page": r.page, "text": r.text, "score": r.score}
        for r in results
        if r.source_type == "manual"
    ]


async def review_queue(
    org_id: uuid.UUID, provider: LLMProvider | None = None
) -> list[ReviewItem]:
    """Pending fixes with everything a curator needs to decide (FR-15).

    For each fix: the original question and answer, the proposed text, the top
    manual chunks for context, and the AI pre-screen advisory. The pre-screen is
    generated lazily on first view and persisted to `ai_prescreen_report` so it
    is computed once per fix, not on every queue fetch.
    """
    org_id = uuid.UUID(str(org_id))
    async with session_for_org(org_id) as s:
        fixes = (
            (
                await s.execute(
                    select(Fix)
                    .where(Fix.state == "pending_review")
                    .order_by(Fix.created_at)
                )
            )
            .scalars()
            .all()
        )
        answer_by_log: dict[uuid.UUID, str] = {}
        log_ids = [f.answer_log_id for f in fixes if f.answer_log_id]
        if log_ids:
            for log in (
                (await s.execute(select(AnswerLog).where(AnswerLog.id.in_(log_ids))))
                .scalars()
                .all()
            ):
                answer_by_log[log.id] = log.answer_text

        items: list[ReviewItem] = []
        for fix in fixes:
            query = fix.question_text or fix.proposed_text
            manual = await _top_manual_chunks(org_id, fix.equipment_id, query)
            if fix.ai_prescreen_report is None:
                report = await prescreen(
                    fix.proposed_text, [c["text"] for c in manual], provider=provider
                )
                fix.ai_prescreen_report = report
                s.add(
                    AuditEvent(
                        organization_id=org_id,
                        actor_id=None,
                        entity_type="fix",
                        entity_id=fix.id,
                        action="prescreen",
                        before=None,
                        after=report,
                    )
                )
            items.append(
                ReviewItem(
                    fix_id=fix.id,
                    state=fix.state,
                    question=fix.question_text,
                    original_answer=answer_by_log.get(fix.answer_log_id),
                    proposed_text=fix.proposed_text,
                    submitted_by=fix.submitted_by,
                    equipment_id=fix.equipment_id,
                    manual_chunks=[
                        {**c, "chunk_id": str(c["chunk_id"])} for c in manual
                    ],
                    prescreen=fix.ai_prescreen_report,
                    created_at=fix.created_at,
                )
            )
        await s.commit()
        return items


async def _index_fix_text(s, org_id: uuid.UUID, fix: Fix, text: str) -> None:
    """Embed `text` into field_fix chunks for `fix` (spec §2.4 approved-fix moat).

    The index is the single source of truth: callers that change an approved
    fix's served text must delete its existing chunks first, then re-index here.
    """
    text_chunks = chunk_pages([(0, text)])
    embeddings = await embed([c.text for c in text_chunks])
    for tc, vector in zip(text_chunks, embeddings):
        s.add(
            Chunk(
                organization_id=org_id,
                document_id=None,
                source_type="field_fix",
                content=tc.text,
                page=None,
                fix_id=fix.id,
                embedding=vector,
            )
        )


async def list_fixes(
    org_id: uuid.UUID, states: tuple[str, ...] | None = None
) -> list[FixSummary]:
    """All fixes (optionally filtered by state) with submitter/reviewer names.

    Powers the console's "all items" table (date, creator, approved). Unlike
    review_queue this never triggers a pre-screen — it is a read-only listing.
    """
    org_id = uuid.UUID(str(org_id))
    async with session_for_org(org_id) as s:
        stmt = select(Fix).order_by(Fix.created_at.desc())
        if states:
            stmt = stmt.where(Fix.state.in_(states))
        fixes = (await s.execute(stmt)).scalars().all()

        user_ids = {f.submitted_by for f in fixes} | {
            f.reviewed_by for f in fixes if f.reviewed_by
        }
        names: dict[uuid.UUID, str] = {}
        if user_ids:
            for u in (
                (await s.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
            ):
                names[u.id] = u.name

        return [
            FixSummary(
                fix_id=f.id,
                state=f.state,
                question=f.question_text,
                proposed_text=f.proposed_text,
                equipment_id=f.equipment_id,
                submitted_by=f.submitted_by,
                submitted_by_name=names.get(f.submitted_by),
                reviewed_by=f.reviewed_by,
                reviewed_by_name=names.get(f.reviewed_by) if f.reviewed_by else None,
                review_notes=f.review_notes,
                approved_at=f.approved_at,
                created_at=f.created_at,
                updated_at=f.updated_at,
            )
            for f in fixes
        ]


async def create_fix(
    org_id: uuid.UUID,
    equipment_id: uuid.UUID,
    actor_id: uuid.UUID,
    role: str,
    proposed_text: str,
    question: str | None = None,
) -> uuid.UUID:
    """Curator/admin opens a new candidate fix directly into review (FR-15).

    Like a technician submission it lands in pending_review and is never indexed
    until approved — humans approve, nothing is auto-served (spec §2.5).
    """
    _require_reviewer(role)
    org_id = uuid.UUID(str(org_id))
    text = proposed_text.strip()
    if not text:
        raise ValueError("proposed_text must not be empty")
    async with session_for_org(org_id) as s:
        fix = Fix(
            organization_id=org_id,
            equipment_id=equipment_id,
            question_text=question,
            proposed_text=text,
            submitted_by=actor_id,
            state="pending_review",
        )
        s.add(fix)
        await s.flush()
        s.add(
            AuditEvent(
                organization_id=org_id,
                actor_id=actor_id,
                entity_type="fix",
                entity_id=fix.id,
                action="create",
                before=None,
                after={"state": "pending_review", "proposed_text": text},
            )
        )
        await s.commit()
        return fix.id


async def update_fix(
    org_id: uuid.UUID,
    fix_id: uuid.UUID,
    actor_id: uuid.UUID,
    role: str,
    proposed_text: str | None = None,
    question: str | None = None,
) -> None:
    """Edit a fix's text/question. If approved, re-index so the moat stays true.

    The vector index is the single source of truth (spec §2.4): editing an
    approved fix's served text must atomically replace its field_fix chunks.
    """
    _require_reviewer(role)
    org_id = uuid.UUID(str(org_id))
    new_text = proposed_text.strip() if proposed_text is not None else None
    if new_text == "":
        raise ValueError("proposed_text must not be empty")
    async with session_for_org(org_id) as s:
        fix = await s.get(Fix, fix_id)
        if fix is None:
            raise FixNotFound(str(fix_id))
        before = {"proposed_text": fix.proposed_text, "question_text": fix.question_text}
        if new_text is not None:
            fix.proposed_text = new_text
        if question is not None:
            fix.question_text = question
        fix.updated_at = func.now()

        if new_text is not None and fix.state == "approved":
            await s.execute(delete(Chunk).where(Chunk.fix_id == fix.id))
            await s.flush()
            await _index_fix_text(s, org_id, fix, new_text)

        s.add(
            AuditEvent(
                organization_id=org_id,
                actor_id=actor_id,
                entity_type="fix",
                entity_id=fix.id,
                action="edit",
                before=before,
                after={"proposed_text": fix.proposed_text, "question_text": fix.question_text},
            )
        )
        await s.commit()


async def delete_fix(
    org_id: uuid.UUID, fix_id: uuid.UUID, actor_id: uuid.UUID, role: str
) -> None:
    """Delete a fix and its index chunks (chunks cascade on fix delete).

    Removing the row removes it from retrieval immediately (single source of
    truth, spec §2.4). The audit row survives the deletion (24-month retention).
    """
    _require_reviewer(role)
    org_id = uuid.UUID(str(org_id))
    async with session_for_org(org_id) as s:
        fix = await s.get(Fix, fix_id)
        if fix is None:
            raise FixNotFound(str(fix_id))
        s.add(
            AuditEvent(
                organization_id=org_id,
                actor_id=actor_id,
                entity_type="fix",
                entity_id=fix.id,
                action="delete",
                before={"state": fix.state, "proposed_text": fix.proposed_text},
                after=None,
            )
        )
        await s.delete(fix)
        await s.commit()


async def _load_for_transition(s, fix_id: uuid.UUID, dst: str) -> Fix:
    """Load a fix and verify the ``current -> dst`` state change is legal.

    Raises ``FixNotFound`` or ``IllegalTransition`` so every mutating action
    shares one consistent guard.
    """
    fix = await s.get(Fix, fix_id)
    if fix is None:
        raise FixNotFound(str(fix_id))
    if not can_transition(fix.state, dst):
        raise IllegalTransition(f"{fix.state} -> {dst}")
    return fix


async def approve(
    org_id: uuid.UUID,
    fix_id: uuid.UUID,
    curator_id: uuid.UUID,
    role: str,
    edited_text: str | None = None,
) -> None:
    """Approve a fix and index it as a field_fix chunk (FR-16/FR-18, spec §2.4).

    Indexing the approved text into `chunks` (source_type='field_fix') is what
    makes the fix retrievable and lets it outrank manual content on symptom match
    — the approved-fix moat. The index is the single source of truth.
    """
    _require_reviewer(role)
    org_id = uuid.UUID(str(org_id))
    text = (edited_text or "").strip() or None
    async with session_for_org(org_id) as s:
        fix = await _load_for_transition(s, fix_id, "approved")
        before = {"state": fix.state, "proposed_text": fix.proposed_text}

        final_text = text or fix.proposed_text
        await _index_fix_text(s, org_id, fix, final_text)

        fix.proposed_text = final_text
        fix.state = "approved"
        fix.reviewed_by = curator_id
        fix.approved_at = func.now()
        s.add(
            AuditEvent(
                organization_id=org_id,
                actor_id=curator_id,
                entity_type="fix",
                entity_id=fix.id,
                action="approve",
                before=before,
                after={
                    "state": "approved",
                    "proposed_text": final_text,
                    "edited": text is not None,
                },
            )
        )
        await s.commit()


async def _resolve(
    org_id: uuid.UUID,
    fix_id: uuid.UUID,
    curator_id: uuid.UUID,
    role: str,
    dst: str,
    reason: str,
) -> None:
    """Shared implementation for reject/unsafe: set the state and record the reason."""
    _require_reviewer(role)
    org_id = uuid.UUID(str(org_id))
    async with session_for_org(org_id) as s:
        fix = await _load_for_transition(s, fix_id, dst)
        before = {"state": fix.state}
        fix.state = dst
        fix.reviewed_by = curator_id
        fix.review_notes = reason
        s.add(
            AuditEvent(
                organization_id=org_id,
                actor_id=curator_id,
                entity_type="fix",
                entity_id=fix.id,
                action=dst,
                before=before,
                after={"state": dst, "reason": reason},
            )
        )
        await s.commit()


async def reject(
    org_id: uuid.UUID, fix_id: uuid.UUID, curator_id: uuid.UUID, role: str, reason: str
) -> None:
    """Reject a fix; reason is stored for submitter visibility (FR-18)."""
    await _resolve(org_id, fix_id, curator_id, role, "rejected", reason)


async def flag_unsafe(
    org_id: uuid.UUID, fix_id: uuid.UUID, curator_id: uuid.UUID, role: str, reason: str
) -> None:
    """Flag a fix unsafe; terminal for the submission, reason recorded (FR-18)."""
    await _resolve(org_id, fix_id, curator_id, role, "unsafe", reason)


async def retire(
    org_id: uuid.UUID, fix_id: uuid.UUID, actor_id: uuid.UUID, role: str, reason: str
) -> None:
    """Retire an approved fix and delete its index chunks in one transaction.

    The vector index is the single source of truth (spec §2.4): a retired fix
    must vanish from retrieval immediately, so its field_fix chunks are removed
    atomically with the state change.
    """
    _require_reviewer(role)
    org_id = uuid.UUID(str(org_id))
    async with session_for_org(org_id) as s:
        fix = await _load_for_transition(s, fix_id, "retired")
        before = {"state": fix.state}
        await s.execute(delete(Chunk).where(Chunk.fix_id == fix.id))
        fix.state = "retired"
        fix.reviewed_by = actor_id
        fix.review_notes = reason
        s.add(
            AuditEvent(
                organization_id=org_id,
                actor_id=actor_id,
                entity_type="fix",
                entity_id=fix.id,
                action="retire",
                before=before,
                after={"state": "retired", "reason": reason},
            )
        )
        await s.commit()
