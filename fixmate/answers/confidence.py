"""Maps a retrieval score to a confidence band that gates whether we answer.

The pipeline asks: "how good was our best matching source?" If the answer is
"not good enough" (band ``low``), it refuses to generate an answer and escalates
to a human instead (FR-4). This single, conservative cutoff is the first safety
gate — keeping weakly-supported answers away from technicians.
"""

# Confidence thresholds map the top rerank score (BGE-M3 cosine in [0,1]) to a
# band. `low` forces the FR-4 "don't know + escalate" path instead of an LLM
# answer. SAFETY-CRITICAL (Appendix A.8): these cutoffs are initial values —
# calibrate only with Phase 12 eval evidence; never lower without it, because a
# lower bar lets weakly-grounded answers reach technicians.
HIGH_THRESHOLD = 0.70
MEDIUM_THRESHOLD = 0.45


def confidence_band(top_score: float | None) -> str:
    """Classify the best retrieval score into ``"high"`` / ``"medium"`` / ``"low"``.

    ``None`` (no results at all) is treated as ``"low"``.
    """
    if top_score is None:
        return "low"
    if top_score >= HIGH_THRESHOLD:
        return "high"
    if top_score >= MEDIUM_THRESHOLD:
        return "medium"
    return "low"
