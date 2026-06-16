"""Builds a deterministic demo tenant used by evals and demo seeding.

Both the eval runner and ``scripts/seed_demo.py`` need a known, repeatable
dataset: one equipment profile, a small manual with specific anchors (error code
E47, torque 12 Nm, pressure 2 bar, part AB-1234, LOTO steps), three users, and
one approved field fix. The manual text is crafted so the eval cases can assert
groundedness against it, so do not change those anchor strings casually. The
builder is idempotent — re-running reuses existing rows so chunk ids stay stable.
"""

import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

import fitz
from sqlalchemy import select

from fixmate.core.db import session_for_org
from fixmate.core.models import Fix, User
from fixmate.curation.service import approve
from fixmate.ingestion import registry
from fixmate.ingestion.pipeline import ingest_document
from fixmate.llm.base import LLMProvider

# A self-contained demo manual for one piece of equipment. It carries the
# anchors the safety eval and the regression baseline depend on: an error code
# (E47), a torque spec (12 Nm), a pressure (2 bar), a part number (AB-1234) and
# explicit LOTO/depressurization safety steps. Keep these verbatim — the eval
# cases assert grounding against them.
DEMO_EQUIPMENT = "Pump X"
DEMO_MANUAL_TITLE = "Pump X Service Manual"
DEMO_MANUAL_PAGES = {
    1: (
        "FixMate demo: dialysate concentrate Pump X service manual. "
        "Always perform lockout/tagout (LOTO) and depressurize the circuit "
        "before opening any housing."
    ),
    2: (
        "Error E47: concentrate valve blocked. The dialysate concentrate valve "
        "has scaled shut. Inspect the valve seat for scale buildup and replace "
        "seal kit part AB-1234 if the seat is pitted."
    ),
    3: (
        "Reassembly. Tighten the housing bolts to 12 Nm in a star pattern. Do "
        "not exceed 12 Nm or the housing will crack. Set inlet pressure to 2 bar."
    ),
}

# Field fix indexed for the E47 symptom — proves the approved-fix moat: once
# approved it outranks the manual chunk and is served with a verification badge.
DEMO_FIX_QUESTION = "How do I clear error E47?"
DEMO_FIX_TEXT = (
    "Error E47 — concentrate valve blocked: perform LOTO and depressurize the "
    "circuit, remove the valve cartridge, clear scale from the seat, and refit "
    "the AB-1234 seal kit. This clears E47 reliably."
)


@dataclass
class DemoTenant:
    """Handles to the key rows of a built demo tenant (ids for org, equipment,
    the three users, the ingested manual, and the approved fix)."""

    org_id: uuid.UUID
    equipment_id: uuid.UUID
    admin_id: uuid.UUID
    curator_id: uuid.UUID
    tech_id: uuid.UUID
    document_id: uuid.UUID | None
    approved_fix_id: uuid.UUID


def build_demo_pdf(path: Path) -> Path:
    """Write the demo manual (text pages + one image on page 2) to ``path``."""
    doc = fitz.open()
    for page_no in sorted(DEMO_MANUAL_PAGES):
        page = doc.new_page()
        page.insert_text((72, 72), DEMO_MANUAL_PAGES[page_no], fontsize=11)
        if page_no == 2:
            pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 64, 64))
            pix.set_rect(pix.irect, (200, 40, 40))
            page.insert_image(fitz.Rect(72, 130, 200, 258), pixmap=pix)
    doc.save(path)
    doc.close()
    return path


async def _get_or_create_user(s, org_id: uuid.UUID, name: str, role: str) -> uuid.UUID:
    """Return the id of the named user in this org, creating with ``role`` if absent."""
    uid = await s.scalar(select(User.id).where(User.organization_id == org_id, User.name == name))
    if uid:
        return uid
    user = User(organization_id=org_id, name=name, role=role)
    s.add(user)
    await s.flush()
    return user.id


async def build_demo_tenant(org_name: str, *, provider: LLMProvider | None = None) -> DemoTenant:
    """Build (or reuse) a demo tenant: equipment, ingested manual, one approved fix.

    Idempotent by design — the manual is re-used if its title already exists and
    the approved fix is re-used if one already exists for the equipment. Both the
    human demo (`scripts/seed_demo.py`) and the eval runner call this; making it
    idempotent keeps chunk ids stable across runs so the regression baseline
    (`fixmate/evals/baseline.jsonl`) stays meaningful between invocations.
    """
    org_id = await registry.get_or_create_org(org_name)

    async with session_for_org(org_id) as s:
        equipment_id = await registry.get_or_create_equipment(s, org_id, DEMO_EQUIPMENT)
        admin_id = await _get_or_create_user(s, org_id, "Auto Admin", "admin")
        curator_id = await _get_or_create_user(s, org_id, "Cora Curator", "curator")
        tech_id = await _get_or_create_user(s, org_id, "Tina Tech", "tech")
        existing_doc = await registry.latest_document(s, org_id, equipment_id, DEMO_MANUAL_TITLE)
        document_id = existing_doc.id if existing_doc else None
        await s.commit()

    if document_id is None:
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = build_demo_pdf(Path(tmp) / "pump-x-manual.pdf")
            document_id = await ingest_document(
                org_id, equipment_id, pdf_path, title=DEMO_MANUAL_TITLE, provider=provider
            )

    async with session_for_org(org_id) as s:
        approved_fix_id = await s.scalar(
            select(Fix.id).where(Fix.equipment_id == equipment_id, Fix.state == "approved")
        )
        if approved_fix_id is None:
            fix = Fix(
                organization_id=org_id,
                equipment_id=equipment_id,
                question_text=DEMO_FIX_QUESTION,
                proposed_text=DEMO_FIX_TEXT,
                submitted_by=tech_id,
                state="pending_review",
            )
            s.add(fix)
            await s.commit()
            new_fix_id = fix.id
        else:
            new_fix_id = None

    if new_fix_id is not None:
        await approve(org_id, new_fix_id, curator_id, "curator")
        approved_fix_id = new_fix_id

    return DemoTenant(
        org_id=org_id,
        equipment_id=equipment_id,
        admin_id=admin_id,
        curator_id=curator_id,
        tech_id=tech_id,
        document_id=document_id,
        approved_fix_id=approved_fix_id,
    )
