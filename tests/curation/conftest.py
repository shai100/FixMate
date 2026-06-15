from dataclasses import dataclass

import pytest

from fixmate.core.db import session_for_org
from fixmate.core.models import AnswerLog, EquipmentProfile, Fix, User
from fixmate.ingestion.pipeline import ingest_document

# Reuse the retrieval suite's sample PDF builder (manual chunks incl. E47).
from tests.retrieval.conftest import sample_pdf  # noqa: F401


@dataclass
class CurationWorld:
    org_id: object
    other_org_id: object
    equipment_id: object
    curator_id: object
    tech_id: object
    fix_id: object
    answer_log_id: object


@pytest.fixture
async def curation_world(two_orgs, sample_pdf) -> CurationWorld:
    """A tenant with the sample manual ingested and one pending_review fix.

    The fix targets error E47 — the same symptom the manual covers — so the moat
    test can prove an approved field fix outranks the manual chunk on that query.
    """
    org_a, org_b = two_orgs
    async with session_for_org(org_a) as s:
        curator = User(organization_id=org_a, name="Cora Curator", role="curator")
        tech = User(organization_id=org_a, name="Tina Tech", role="tech")
        eq = EquipmentProfile(organization_id=org_a, name="Pump X")
        s.add_all([curator, tech, eq])
        await s.flush()
        curator_id, tech_id, eq_id = curator.id, tech.id, eq.id

        log = AnswerLog(
            organization_id=org_a,
            question="How do I clear error E47?",
            answer_text="I don't have a confident answer; please escalate.",
            model_version="escalation",
            provider="none",
            confidence="low",
        )
        s.add(log)
        await s.flush()
        log_id = log.id

        fix = Fix(
            organization_id=org_a,
            equipment_id=eq_id,
            question_text="How do I clear error E47?",
            answer_log_id=log_id,
            proposed_text=(
                "Error E47 concentrate valve blocked: remove the valve cartridge, "
                "clear scale from the seat, and refit. This clears E47 reliably."
            ),
            submitted_by=tech_id,
            state="pending_review",
        )
        s.add(fix)
        await s.commit()
        fix_id = fix.id

    await ingest_document(org_a, eq_id, sample_pdf)

    return CurationWorld(
        org_id=org_a,
        other_org_id=org_b,
        equipment_id=eq_id,
        curator_id=curator_id,
        tech_id=tech_id,
        fix_id=fix_id,
        answer_log_id=log_id,
    )
