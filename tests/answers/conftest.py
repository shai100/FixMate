import pytest

from fixmate.core.db import session_for_org
from fixmate.core.models import EquipmentProfile
from fixmate.ingestion.pipeline import ingest_document

# Reuse the retrieval suite's sample PDF builder.
from tests.retrieval.conftest import sample_pdf  # noqa: F401


@pytest.fixture
async def ingested_org(two_orgs, sample_pdf):
    """One tenant with the sample manual ingested; returns (org_id, equipment_id)."""
    org_id, _ = two_orgs
    async with session_for_org(org_id) as s:
        eq = EquipmentProfile(organization_id=org_id, name="Pump X")
        s.add(eq)
        await s.commit()
        eq_id = eq.id
    await ingest_document(org_id, eq_id, sample_pdf)
    return org_id, eq_id
