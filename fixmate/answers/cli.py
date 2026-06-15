import argparse
import asyncio

from fixmate.answers.composer import compose_answer
from fixmate.core.db import session_for_org
from fixmate.ingestion import registry


async def _run(question: str, org_name: str, equipment_name: str | None) -> None:
    org_id = await registry.get_or_create_org(org_name)

    equipment_id = None
    if equipment_name:
        async with session_for_org(org_id) as s:
            equipment_id = await registry.get_or_create_equipment(s, org_id, equipment_name)
            await s.commit()

    answer = await compose_answer(org_id, equipment_id, question)

    print(f"\n[{answer.confidence}]{' ESCALATED' if answer.escalated else ''}\n")
    print(answer.text)
    if answer.citations:
        print("\nCitations:")
        for c in answer.citations:
            page = "" if c.page is None else f" p{c.page}"
            print(f"  - {c.source_type}{page} (chunk {c.chunk_id})")
    if answer.figures:
        print("\nFigures:")
        for f in answer.figures:
            print(f"  - p{f['page']}: {f['caption']}")
    print(f"\nanswer_log_id: {answer.answer_log_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compose a grounded, cited answer.")
    parser.add_argument("question")
    parser.add_argument("--org", required=True, help="organization name")
    parser.add_argument("--equipment", help="restrict to one equipment profile")
    args = parser.parse_args()
    asyncio.run(_run(args.question, args.org, args.equipment))


if __name__ == "__main__":
    main()
