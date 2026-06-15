# Confidence thresholds map the top rerank score (BGE-M3 cosine in [0,1]) to a
# band. `low` forces the FR-4 "don't know + escalate" path instead of an LLM
# answer. SAFETY-CRITICAL (Appendix A.8): these cutoffs are initial values —
# calibrate only with Phase 12 eval evidence; never lower without it, because a
# lower bar lets weakly-grounded answers reach technicians.
HIGH_THRESHOLD = 0.70
MEDIUM_THRESHOLD = 0.45


def confidence_band(top_score: float | None) -> str:
    if top_score is None:
        return "low"
    if top_score >= HIGH_THRESHOLD:
        return "high"
    if top_score >= MEDIUM_THRESHOLD:
        return "medium"
    return "low"
