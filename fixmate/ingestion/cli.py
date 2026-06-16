"""Command-line tool to ingest a PDF manual for a tenant.

Run it inline (does the work in-process and prints chunk/figure counts) or with
``--async`` to enqueue the Celery task instead. Example: ``python -m
fixmate.ingestion.cli manual.pdf --org "FixMate Demo" --equipment "Pump X"``.
"""

import argparse
import asyncio

from sqlalchemy import func, select

from fixmate.core.db import session_for_org
from fixmate.core.models import Chunk, Figure
from fixmate.ingestion import registry
from fixmate.ingestion.pipeline import ingest_document


async def _run(pdf_path: str, org_name: str, equipment_name: str, run_async: bool) -> None:
    """Resolve org/equipment, then ingest the PDF (inline or via Celery)."""
    org_id = await registry.get_or_create_org(org_name)
    async with session_for_org(org_id) as s:
        equipment_id = await registry.get_or_create_equipment(s, org_id, equipment_name)
        await s.commit()

    if run_async:
        # Imported lazily so the sync path never requires a reachable broker.
        from fixmate.ingestion.tasks import ingest_document_task

        result = ingest_document_task.delay(str(org_id), str(equipment_id), pdf_path)
        print(f"enqueued task {result.id} (org={org_name}, equipment={equipment_name})")
        return

    doc_id = await ingest_document(org_id, equipment_id, pdf_path)
    async with session_for_org(org_id) as s:
        n_chunks = await s.scalar(
            select(func.count()).select_from(Chunk).where(Chunk.document_id == doc_id)
        )
        n_figures = await s.scalar(
            select(func.count()).select_from(Figure).where(Figure.document_id == doc_id)
        )
    print(f"ingested document {doc_id}: {n_chunks} chunks, {n_figures} figures")


def main() -> None:
    """Parse CLI arguments and run ingestion."""
    parser = argparse.ArgumentParser(description="Ingest a PDF manual for a tenant.")
    parser.add_argument("pdf_path")
    parser.add_argument("--org", required=True, help="organization name (created if missing)")
    parser.add_argument(
        "--equipment", required=True, help="equipment profile name (created if missing)"
    )
    parser.add_argument(
        "--async", dest="run_async", action="store_true", help="enqueue via Celery instead"
    )
    args = parser.parse_args()
    asyncio.run(_run(args.pdf_path, args.org, args.equipment, args.run_async))


if __name__ == "__main__":
    main()
