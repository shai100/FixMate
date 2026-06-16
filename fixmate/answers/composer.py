"""The RAG (Retrieval-Augmented Generation) answer pipeline — FixMate's core.

This module turns a technician's question into a safe, grounded, cited answer.
"RAG" means: instead of asking the LLM to answer from memory (which could
fabricate dangerous specs), we first *retrieve* relevant passages from the
customer's own manuals/fixes, then ask the LLM to answer *only* from those
passages. Several safety gates wrap that core step:

  1. **Retrieve** the most relevant chunks (``fixmate/retrieval/service.py``).
  2. **Confidence gate** — if the best match is weak, don't even ask the LLM;
     return an escalation response (FR-4).
  3. **Compose** — prompt the LLM with the sources and the question.
  4. **Citation + groundedness validation** — every numeric/part claim must
     appear in the sources and every citation must point at a retrieved chunk.
     If not, retry once with feedback; if it still fails, escalate.
  5. **Log** the whole thing immutably (``AnswerLog``) for audit/regression.

The public entry point is ``compose_answer``; everything else here supports it.
"""

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select

from fixmate.answers import prompts
from fixmate.answers.answer_log import write_answer_log
from fixmate.answers.confidence import confidence_band
from fixmate.answers.groundedness import check_groundedness
from fixmate.core import storage
from fixmate.core.db import session_for_org
from fixmate.core.models import Figure, Fix, User
from fixmate.llm.base import CompletionRequest, LLMProvider
from fixmate.llm.factory import get_provider
from fixmate.retrieval.service import ScoredChunk, search

# Citation marker `[chunk:<id>]` (Appendix A.7). The full id is a 36-char UUID,
# but small local models (qwen3:4b) routinely cite only the leading hex segment
# (e.g. `[chunk:0eca1ad9]`). Accept 4–36 hex/`-` chars here and resolve the token
# against the retrieved set in `_resolve_citations`, so an abbreviated-but-
# unambiguous citation still grounds instead of forcing a needless escalation.
_CITATION = re.compile(r"\[chunk:([0-9a-fA-F][0-9a-fA-F-]{3,35})\]")


@dataclass
class Citation:
    """One source backing a claim: which chunk, from which document/page, and
    whether it came from a manual or a field fix."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID | None
    source_type: str
    page: int | None


@dataclass
class Answer:
    """The complete result of ``compose_answer``.

    ``escalated`` is True when the pipeline declined to answer (low confidence or
    failed grounding) and returned an escalation message instead. ``answer_log_id``
    ties this answer to its immutable audit record.
    """

    text: str
    confidence: str
    citations: list[Citation]
    figures: list[dict]
    escalated: bool
    answer_log_id: uuid.UUID


def _parse_cited_tokens(text: str) -> list[str]:
    """Extract the distinct ``[chunk:<id>]`` tokens an answer cites, in order."""
    seen: list[str] = []
    for m in _CITATION.finditer(text):
        tok = m.group(1).lower()
        if tok not in seen:
            seen.append(tok)
    return seen


def _resolve_citations(text: str, by_id: dict[str, ScoredChunk]) -> tuple[list[str], list[str]]:
    """Map citation tokens in `text` to full retrieved chunk ids.

    A token resolves when it equals a retrieved id, or is an unambiguous prefix of
    exactly one retrieved id (handles the abbreviated-UUID citations local models
    emit). Ambiguous or unknown tokens are returned as invalid so the composer can
    retry or escalate — an answer must never cite outside the retrieved set.
    """
    valid: list[str] = []
    invalid: list[str] = []
    for tok in _parse_cited_tokens(text):
        if tok in by_id:
            if tok not in valid:
                valid.append(tok)
            continue
        matches = [cid for cid in by_id if cid.startswith(tok)]
        if len(matches) == 1:
            if matches[0] not in valid:
                valid.append(matches[0])
        else:
            invalid.append(tok)
    return valid, invalid


async def _fix_badges(
    session, chunks: list[ScoredChunk]
) -> dict[str, tuple[str | None, str | None]]:
    """Look up the verification badge (approver name + approval date) for any
    field-fix chunks, so the prompt can present them as human-verified."""
    fix_ids = [c.fix_id for c in chunks if c.source_type == "field_fix" and c.fix_id]
    if not fix_ids:
        return {}
    rows = (
        await session.execute(
            select(Fix.id, User.name, Fix.approved_at)
            .join(User, User.id == Fix.reviewed_by, isouter=True)
            .where(Fix.id.in_(fix_ids))
        )
    ).all()
    badges: dict[str, tuple[str | None, str | None]] = {}
    for fid, approver, approved_at in rows:
        when = approved_at.date().isoformat() if approved_at else None
        badges[str(fid)] = (approver, when)
    return badges


async def _figures_for(session, chunks: list[ScoredChunk]) -> list[dict]:
    """Collect diagrams that live on the same document pages as the retrieved
    chunks, each with a fresh signed URL, so the answer can show relevant images."""
    pairs = {(c.document_id, c.page) for c in chunks if c.document_id and c.page is not None}
    if not pairs:
        return []
    doc_ids = {d for d, _ in pairs}
    pages = {p for _, p in pairs}
    rows = (
        (
            await session.execute(
                select(Figure).where(Figure.document_id.in_(doc_ids), Figure.page.in_(pages))
            )
        )
        .scalars()
        .all()
    )
    return [
        {"page": f.page, "caption": f.caption, "url": storage.presigned_url(f.storage_key)}
        for f in rows
        if (f.document_id, f.page) in pairs
    ]


async def compose_answer(
    org_id: uuid.UUID,
    equipment_id: uuid.UUID | None,
    question: str,
    history: list[dict] = None,
    *,
    conversation_id: uuid.UUID | None = None,
    provider: LLMProvider | None = None,
) -> Answer:
    """Answer one question end-to-end and return a grounded ``Answer`` (plan §5.5).

    Pipeline: search -> confidence gate -> LLM compose -> citation validation ->
    groundedness check (retry once, then escalate) -> log. The function always
    writes an ``AnswerLog`` and always returns an ``Answer`` (a low-confidence or
    ungrounded result comes back with ``escalated=True`` and an escalation
    message rather than raising).

    Args:
        org_id: Tenant the question belongs to (scopes retrieval + logging).
        equipment_id: Optional equipment to restrict retrieval to.
        question: The technician's question.
        history: Prior conversation turns (``[{"role", "content"}, ...]``) for
            multi-turn context.
        conversation_id: Conversation to attach the answer log to, if any.
        provider: LLM backend override; defaults to the configured provider.
    """
    history = history or []
    org_id = uuid.UUID(str(org_id))
    provider = provider or get_provider()

    results = await search(org_id, equipment_id, question)
    top_score = results[0].score if results else None
    confidence = confidence_band(top_score)
    chunk_texts = [c.text for c in results]
    retrieved_ids = [c.chunk_id for c in results]
    by_id = {str(c.chunk_id): c for c in results}

    async with session_for_org(org_id) as s:
        figures = await _figures_for(s, results) if results else []

        if confidence == "low":
            text = prompts.escalation_answer(results)
            log_id = await write_answer_log(
                s,
                org_id=org_id,
                question=question,
                answer_text=text,
                retrieved_chunk_ids=retrieved_ids,
                model_version="escalation",
                provider="none",
                confidence=confidence,
                citations=[],
                groundedness={"checked": False, "reason": "low_confidence_escalation"},
                tokens_used=0,
                conversation_id=conversation_id,
            )
            await s.commit()
            return Answer(text, confidence, [], figures, escalated=True, answer_log_id=log_id)

        badges = await _fix_badges(s, results)
        system = prompts.SYSTEM_PROMPT
        user_prompt = prompts.build_user_prompt(question, results, badges)
        messages = [*history, {"role": "user", "content": user_prompt}]

        grounded = False
        abstained = False
        violations: list[str] = []
        valid_cited: list[str] = []
        result_text = ""
        tokens = 0
        model_version = ""
        provider_name = ""
        attempt_messages = messages
        for _ in range(2):
            completion = await provider.complete(
                CompletionRequest(system=system, messages=attempt_messages)
            )
            result_text = completion.text
            tokens += completion.tokens_used
            model_version = completion.model_version
            provider_name = completion.provider

            # Structured abstention: the model declared the SOURCES insufficient.
            # Don't retry — escalate (FR-4). This is the reliable out-of-corpus
            # gate; score-based confidence cannot separate weak matches on small
            # corpora and the LLM may otherwise cite irrelevant chunks.
            if prompts.ABSTAIN_SENTINEL in result_text.upper():
                abstained = True
                break

            valid_cited, invalid = _resolve_citations(result_text, by_id)
            grounded_ok, violations = check_groundedness(result_text, chunk_texts)
            # A non-escalated answer must be both grounded and citable: every
            # claim traceable to a retrieved chunk (CLAUDE.md §4.2). An answer
            # with no valid citation is effectively a refusal — escalate it
            # rather than show an uncited answer to a technician.
            if grounded_ok and not invalid and valid_cited:
                grounded = True
                break
            retry_problems = list(violations) + [f"[chunk:{cid}]" for cid in invalid]
            if not valid_cited:
                retry_problems.append("no valid [chunk:<id>] citation from the SOURCES")
            attempt_messages = [
                *messages,
                {"role": "assistant", "content": result_text},
                {"role": "user", "content": prompts.groundedness_retry_suffix(retry_problems)},
            ]

        if not grounded:
            text = prompts.escalation_answer(results)
            groundedness = (
                {"grounded": False, "reason": "model_abstained"}
                if abstained
                else {"grounded": False, "violations": violations}
            )
            log_id = await write_answer_log(
                s,
                org_id=org_id,
                question=question,
                answer_text=text,
                retrieved_chunk_ids=retrieved_ids,
                model_version=model_version,
                provider=provider_name,
                confidence=confidence,
                citations=[],
                groundedness=groundedness,
                tokens_used=tokens,
                conversation_id=conversation_id,
            )
            await s.commit()
            return Answer(text, confidence, [], figures, escalated=True, answer_log_id=log_id)

        cited = [by_id[cid] for cid in valid_cited]
        citations = [Citation(c.chunk_id, c.document_id, c.source_type, c.page) for c in cited]
        citations_json = [
            {
                "chunk_id": str(c.chunk_id),
                "document_id": str(c.document_id) if c.document_id else None,
                "source_type": c.source_type,
                "page": c.page,
            }
            for c in citations
        ]
        log_id = await write_answer_log(
            s,
            org_id=org_id,
            question=question,
            answer_text=result_text,
            retrieved_chunk_ids=retrieved_ids,
            model_version=model_version,
            provider=provider_name,
            confidence=confidence,
            citations=citations_json,
            groundedness={"grounded": True, "violations": []},
            tokens_used=tokens,
            conversation_id=conversation_id,
        )
        await s.commit()
        return Answer(
            text=result_text,
            confidence=confidence,
            citations=citations,
            figures=figures,
            escalated=False,
            answer_log_id=log_id,
        )
