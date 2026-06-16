"""Seed a demo tenant for a 5-minute fresh-machine demo (plan §12.3).

Creates the "FixMate Demo" organization with one equipment profile, ingests the
demo Pump X manual, and approves one field fix for error E47 — enough for the web
chat to answer a real question with citations and surface a field-verified fix.

Run:  python scripts/seed_demo.py
Idempotent: re-running reuses the existing manual and approved fix.
"""

import asyncio

from sqlalchemy import func, select

from fixmate.core.db import session_for_org
from fixmate.core.models import Chunk, Figure
from fixmate.evals.fixtures import build_demo_tenant

DEMO_ORG = "FixMate Demo"


async def _run() -> None:
    print(f"Seeding demo tenant {DEMO_ORG!r}...")
    tenant = await build_demo_tenant(DEMO_ORG)

    async with session_for_org(tenant.org_id) as s:
        manual_chunks = await s.scalar(
            select(func.count()).select_from(Chunk).where(Chunk.source_type == "manual")
        )
        fix_chunks = await s.scalar(
            select(func.count()).select_from(Chunk).where(Chunk.source_type == "field_fix")
        )
        figures = await s.scalar(select(func.count()).select_from(Figure))

    print("\nDemo tenant ready:")
    print(f"  organization_id : {tenant.org_id}")
    print(f"  equipment_id    : {tenant.equipment_id}  (Pump X)")
    print(f"  admin_id        : {tenant.admin_id}")
    print(f"  curator_id      : {tenant.curator_id}")
    print(f"  tech_id         : {tenant.tech_id}")
    print(f"  document_id     : {tenant.document_id}")
    print(f"  approved_fix_id : {tenant.approved_fix_id}")
    print(f"  manual chunks   : {manual_chunks}")
    print(f"  field_fix chunks: {fix_chunks}")
    print(f"  figures         : {figures}")
    print("\nTry it:")
    print(f'  python -m fixmate.answers.cli "How do I fix error E47?" --org "{DEMO_ORG}"')
    print(
        "  or set X-Org-Id to the organization_id above in the web client "
        "(localStorage) and ask in chat."
    )


if __name__ == "__main__":
    asyncio.run(_run())
