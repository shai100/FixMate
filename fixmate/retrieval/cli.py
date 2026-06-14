import argparse
import asyncio

from fixmate.ingestion import registry
from fixmate.retrieval.service import search


async def _run(query: str, org_name: str, equipment_name: str | None, top_k: int) -> None:
    org_id = await registry.get_or_create_org(org_name)

    equipment_id = None
    if equipment_name:
        from fixmate.core.db import session_for_org

        async with session_for_org(org_id) as s:
            equipment_id = await registry.get_or_create_equipment(s, org_id, equipment_name)
            await s.commit()

    results = await search(org_id, equipment_id, query, top_k=top_k)
    if not results:
        print("(no results)")
        return

    print(f"{'score':>6}  {'source':<10} {'page':>4}  text")
    print("-" * 80)
    for r in results:
        snippet = " ".join(r.text.split())[:80]
        page = "" if r.page is None else r.page
        print(f"{r.score:6.3f}  {r.source_type:<10} {page:>4}  {snippet}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Hybrid retrieval over a tenant's index.")
    parser.add_argument("query")
    parser.add_argument("--org", required=True, help="organization name")
    parser.add_argument("--equipment", help="restrict to one equipment profile")
    parser.add_argument("--top-k", type=int, default=8)
    args = parser.parse_args()
    asyncio.run(_run(args.query, args.org, args.equipment, args.top_k))


if __name__ == "__main__":
    main()
