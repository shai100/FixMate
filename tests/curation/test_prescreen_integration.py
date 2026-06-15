import pytest

from fixmate.curation.prescreen import prescreen

pytestmark = pytest.mark.integration

MANUAL = [
    "The pressure relief valve protects the housing. Never operate with it bypassed.",
    "Depressurize the circuit before opening any fitting.",
]


async def test_unsafe_fix_raises_hazard_flag():
    """A fix that bypasses a safety device must surface a hazard advisory (FR-15)."""
    report = await prescreen(
        "Bypass the pressure relief valve so the pump keeps running under load.",
        MANUAL,
    )
    assert "error" not in report
    assert len(report["hazard_flags"]) >= 1
    assert report["overall_risk"] in ("low", "medium", "high")
    # The pre-screen advises only; it never returns an approve/reject decision.
    assert set(report.keys()) == {
        "hazard_flags",
        "contradictions",
        "missing_safety_steps",
        "overall_risk",
    }
