from fixmate.curation.states import can_transition


def test_legal_lifecycle():
    assert can_transition("submitted", "pending_review")
    assert can_transition("pending_review", "approved")
    assert can_transition("pending_review", "rejected")
    assert can_transition("pending_review", "unsafe")
    assert can_transition("approved", "retired")
    assert can_transition("approved", "pending_review")  # FR-19 re-confirmation


def test_illegal_transitions_blocked():
    assert not can_transition("submitted", "approved")  # cannot skip review
    assert not can_transition("rejected", "approved")  # must resubmit
    assert not can_transition("unsafe", "approved")
    assert not can_transition("retired", "approved")
    assert not can_transition("approved", "rejected")
