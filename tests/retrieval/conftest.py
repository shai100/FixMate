import fitz
import pytest

from fixmate.core.db import session_for_org
from fixmate.core.models import EquipmentProfile
from fixmate.ingestion.pipeline import ingest_document

PAGE_TEXT = {
    1: "Maintenance manual. This pump moves dialysate concentrate through the circuit.",
    2: "Error E47: concentrate valve blocked. Inspect the valve seat for scale buildup.",
    3: "Reassembly. Tighten to 12 Nm. Do not exceed torque or the housing will crack.",
}


@pytest.fixture(scope="session")
def sample_pdf(tmp_path_factory):
    path = tmp_path_factory.mktemp("fixtures") / "sample-manual.pdf"
    doc = fitz.open()
    for page_no in (1, 2, 3):
        page = doc.new_page()
        page.insert_text((72, 72), PAGE_TEXT[page_no], fontsize=12)
        if page_no == 2:
            pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 64, 64))
            pix.set_rect(pix.irect, (200, 40, 40))
            page.insert_image(fitz.Rect(72, 120, 200, 248), pixmap=pix)
    doc.save(path)
    doc.close()
    return path


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
