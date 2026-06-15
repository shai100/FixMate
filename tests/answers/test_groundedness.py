from fixmate.answers.groundedness import check_groundedness

CHUNKS = ["Tighten the valve bolts to 12 Nm.", "Use part AB-1234 for the seal."]


def test_grounded_numeric_and_part_claims_pass():
    ok, violations = check_groundedness("Tighten bolts to 12 Nm and fit part AB-1234.", CHUNKS)
    assert ok and violations == []


def test_fabricated_torque_is_rejected():
    ok, violations = check_groundedness("Tighten bolts to 25 Nm.", CHUNKS)
    assert not ok and "25 Nm" in violations[0]


def test_fabricated_part_number_is_rejected():
    ok, violations = check_groundedness("Order part ZZ-9999.", CHUNKS)
    assert not ok


def test_unit_spacing_variation_still_grounded():
    ok, violations = check_groundedness("Torque to 12Nm.", ["Tighten to 12 Nm."])
    assert ok and violations == []
