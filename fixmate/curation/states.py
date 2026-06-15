# Fix lifecycle (Appendix A.5): submitted | pending_review | approved | rejected
# | unsafe | retired. The DB CheckConstraint (Phase 1) and the API payloads
# (Phase 8) reference the same set; this module is the single authority on which
# transitions are legal.
ALLOWED_TRANSITIONS: set[tuple[str, str]] = {
    ("submitted", "pending_review"),
    ("pending_review", "approved"),  # includes curator-edited text (FR-16 Edit & Approve)
    ("pending_review", "rejected"),
    ("pending_review", "unsafe"),
    ("approved", "retired"),
    ("approved", "pending_review"),  # FR-19 aging-fix re-confirmation
}


def can_transition(src: str, dst: str) -> bool:
    return (src, dst) in ALLOWED_TRANSITIONS
