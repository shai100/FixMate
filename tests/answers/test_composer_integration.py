import uuid

import pytest
from sqlalchemy import select

from fixmate.answers.composer import compose_answer
from fixmate.core.db import session_for_org
from fixmate.core.models import AnswerLog

pytestmark = pytest.mark.integration


async def test_grounded_answer_has_citations_and_logs(ingested_org):
    org_id, eq_id = ingested_org
    answer = await compose_answer(org_id, eq_id, "How do I fix error E47?")

    assert answer.text.strip()
    assert not answer.escalated
    assert answer.confidence in ("high", "medium")
    assert len(answer.citations) >= 1

    async with session_for_org(org_id) as s:
        log = await s.get(AnswerLog, answer.answer_log_id)
        assert log is not None
        assert log.retrieved_chunk_ids
        assert log.answer_text == answer.text
        assert log.groundedness["grounded"] is True


async def test_out_of_corpus_question_escalates(ingested_org):
    # An out-of-corpus question escalates: the model cannot ground it in the
    # SOURCES and produces no valid citation, so the composer routes it to the
    # FR-4 escalation path rather than serve an uncited answer (the confidence
    # band is not the only escalation trigger — see composer citation gate).
    org_id, eq_id = ingested_org
    answer = await compose_answer(
        org_id, eq_id, "How do I calibrate the flux capacitor?"
    )
    assert answer.escalated is True
    assert answer.citations == []
    assert "escalate" in answer.text.lower()

    async with session_for_org(org_id) as s:
        log = await s.get(AnswerLog, answer.answer_log_id)
        assert log is not None
        assert log.groundedness["grounded"] is False


async def test_equipment_isolation_yields_escalation(ingested_org):
    org_id, _ = ingested_org
    answer = await compose_answer(org_id, uuid.uuid4(), "How do I fix error E47?")
    assert answer.escalated is True
    assert answer.citations == []
