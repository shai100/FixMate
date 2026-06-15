import pytest

from fixmate.feedback.service import record_feedback
from fixmate.retrieval.service import search

pytestmark = pytest.mark.integration


async def test_submitted_fix_never_surfaces_in_retrieval(feedback_world):
    """End-to-end: a pending candidate fix is invisible to hybrid search (§2.4)."""
    w = feedback_world
    await record_feedback(
        w.org_id,
        w.message_id,
        w.user_id,
        helped=False,
        fix_text="Replace the concentrate valve seat to clear error E47.",
    )

    results = await search(w.org_id, w.equipment_id, "concentrate valve E47")
    assert all(r.source_type != "field_fix" for r in results)
