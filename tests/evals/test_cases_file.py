from fixmate.evals.run import RISK_ORDER, load_cases

VALID_KINDS = {"answer", "prescreen"}
ANSWER_EXPECT_KEYS = {
    "escalated",
    "min_citations",
    "grounded",
    "no_ungrounded_specs",
    "cites_field_fix",
}
PRESCREEN_EXPECT_KEYS = {"min_hazard_flags", "overall_risk_at_least"}


def test_cases_load_and_have_unique_ids():
    cases = load_cases()
    assert cases, "no eval cases defined"
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "duplicate case ids"


def test_every_case_is_well_formed():
    for case in load_cases():
        assert case["kind"] in VALID_KINDS
        expect = case["expect"]
        assert expect, f"{case['id']} has no expectations"
        if case["kind"] == "answer":
            assert "question" in case
            assert set(expect) <= ANSWER_EXPECT_KEYS, f"{case['id']} unknown expect keys"
        else:
            assert "fix_text" in case
            assert set(expect) <= PRESCREEN_EXPECT_KEYS, f"{case['id']} unknown expect keys"
            risk = expect.get("overall_risk_at_least")
            assert risk is None or risk in RISK_ORDER


def test_suite_covers_required_safety_dimensions():
    # CLAUDE.md §4.3 / plan §12.1: the four safety dimensions must each be exercised.
    cases = load_cases()
    expects = [c["expect"] for c in cases]
    assert any(e.get("escalated") is True for e in expects), "missing out-of-corpus escalation"
    assert any("no_ungrounded_specs" in e for e in expects), "missing fabrication gate"
    assert any(e.get("cites_field_fix") for e in expects), "missing approved-fix badging"
    assert any("min_hazard_flags" in e for e in expects), "missing unsafe-fix pre-screen"
