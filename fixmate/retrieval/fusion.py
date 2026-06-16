"""Reciprocal Rank Fusion (RRF) and the approved-fix ranking boost.

RRF is the trick that lets us merge two rankings whose scores aren't comparable
(semantic distance vs. text-rank). Instead of the scores, it uses each item's
*position* in each list: an item near the top of either list scores well, and an
item near the top of *both* scores best. The formula per list is
``1 / (k + rank)``, summed across lists. ``apply_field_fix_boost`` then nudges
approved field fixes above equally-relevant manual content — the product moat.
"""

from collections import defaultdict

RRF_K = 60  # standard RRF constant; rank discount flattens beyond top ~k results


def reciprocal_rank_fusion(
    result_lists: list[list[str]], k: int = RRF_K, with_scores: bool = False
) -> list[str] | dict[str, float]:
    """Merge several ranked id lists by reciprocal-rank fusion.

    RRF uses only rank position, never the underlying scores, so it fuses
    heterogeneous searchers (dense vector + keyword) whose scores are not
    comparable. Returns ids ordered best→worst, or the raw score dict when
    ``with_scores`` (the field-fix boost in service.py operates on scores).
    """
    scores: dict[str, float] = defaultdict(float)
    for results in result_lists:
        for rank, cid in enumerate(results):
            scores[cid] += 1.0 / (k + rank + 1)
    if with_scores:
        return dict(scores)
    return [cid for cid, _ in sorted(scores.items(), key=lambda x: -x[1])]


def apply_field_fix_boost(
    scores: dict[str, float], field_fix_ids: set[str], boost: float = 1.15
) -> dict[str, float]:
    """Multiply the scores of approved field-fix chunks by ``boost``, leaving
    others unchanged — so a verified fix wins ties against manual content."""
    # Approved-fix moat (spec §2.4 / FR-17): field fixes outrank manual content
    # on comparable relevance. 1.15 is an initial value; tune via Phase 12 evals.
    return {cid: s * boost if cid in field_fix_ids else s for cid, s in scores.items()}
