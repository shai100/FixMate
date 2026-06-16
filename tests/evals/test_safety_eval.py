import pytest

from fixmate.evals.fixtures import build_demo_tenant
from fixmate.evals.run import EVAL_ORG, evaluate_case, load_cases, run_evals


@pytest.mark.integration
async def test_all_safety_cases_pass(migrated_db):
    """The full safety suite must pass on the ollama backend (plan §12.1).

    Runs every case through the real services against the eval tenant; any
    failure means a safety regression and fails the build.
    """
    exit_code = await run_evals(record_baseline=False)
    assert exit_code == 0


@pytest.mark.integration
async def test_unsafe_fix_prescreen_flags_hazard(migrated_db):
    # Narrow assertion on the pre-screen path so a failure points straight at it.
    tenant = await build_demo_tenant(EVAL_ORG)
    case = next(c for c in load_cases() if c["id"] == "unsafe_fix_is_flagged")
    reasons = await evaluate_case(tenant, case)
    assert reasons == []


@pytest.mark.integration
async def test_out_of_corpus_question_escalates(migrated_db):
    tenant = await build_demo_tenant(EVAL_ORG)
    case = next(c for c in load_cases() if c["id"] == "out_of_corpus_escalates")
    reasons = await evaluate_case(tenant, case)
    assert reasons == []
