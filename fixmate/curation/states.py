"""The fix lifecycle state machine — the single authority on legal transitions.

A fix moves through a fixed set of states (submitted -> pending_review ->
approved/rejected/unsafe -> retired, with a re-confirmation path back to review).
This module declares exactly which moves are allowed; the curation service checks
``can_transition`` before every state change so an invalid move (e.g. approving a
rejected fix) is impossible. Keeping the rules here, separate from the DB
constraint and the API, means there's one place to read and reason about them.
"""

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
    """Return True if moving a fix from state ``src`` to ``dst`` is allowed."""
    return (src, dst) in ALLOWED_TRANSITIONS
