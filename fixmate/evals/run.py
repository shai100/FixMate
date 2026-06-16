"""The evaluation harness — automated safety + regression checks.

Run with ``python -m fixmate.evals.run``. It builds a known demo tenant, then
runs each case in ``safety_cases.yaml``: "answer" cases assert the pipeline
escalates/grounds/cites as expected; "prescreen" cases assert the safety
pre-screen flags hazards strongly enough. It also compares retrieval against a
recorded baseline (informational drift, never a hard gate). Exit code 0 = all
cases passed, 1 = at least one failed (so CI can gate on it).
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml

from fixmate.answers.composer import compose_answer
from fixmate.answers.groundedness import check_groundedness
from fixmate.curation.prescreen import prescreen
from fixmate.evals.fixtures import DemoTenant, build_demo_tenant
from fixmate.retrieval.service import search

EVAL_ORG = "FixMate Eval"
CASES_PATH = Path(__file__).with_name("safety_cases.yaml")
BASELINE_PATH = Path(__file__).with_name("baseline.jsonl")
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def load_cases() -> list[dict]:
    """Load the list of eval cases from ``safety_cases.yaml``."""
    data = yaml.safe_load(CASES_PATH.read_text(encoding="utf-8"))
    return data["cases"]


async def _eval_answer_case(tenant: DemoTenant, case: dict) -> list[str]:
    """Run one "answer" case and return a list of failure reasons (empty = pass).

    Compares the composed answer against the case's ``expect`` block: escalation,
    citation count, field-fix citation, and groundedness / no-fabricated-specs.
    """
    expect = case["expect"]
    answer = await compose_answer(tenant.org_id, tenant.equipment_id, case["question"])
    reasons: list[str] = []

    if "escalated" in expect and answer.escalated != expect["escalated"]:
        reasons.append(f"escalated={answer.escalated}, expected {expect['escalated']}")
    if "min_citations" in expect and len(answer.citations) < expect["min_citations"]:
        reasons.append(f"{len(answer.citations)} citations < {expect['min_citations']}")
    if expect.get("cites_field_fix") and not any(
        c.source_type == "field_fix" for c in answer.citations
    ):
        reasons.append("no field_fix citation in answer")

    if expect.get("grounded") or expect.get("no_ungrounded_specs"):
        chunks = await search(tenant.org_id, tenant.equipment_id, case["question"])
        grounded_ok, violations = check_groundedness(answer.text, [c.text for c in chunks])
        if expect.get("grounded") and not grounded_ok:
            reasons.append(f"ungrounded claims: {violations}")
        # Fabrication gate: a non-escalated answer must invent no spec/part value.
        if expect.get("no_ungrounded_specs") and not (answer.escalated or grounded_ok):
            reasons.append(f"fabricated specs not in sources: {violations}")
    return reasons


async def _eval_prescreen_case(tenant: DemoTenant, case: dict) -> list[str]:
    """Run one "prescreen" case and return failure reasons (empty = pass).

    Asserts the safety advisory flags enough hazards and rates risk at least as
    high as the case expects.
    """
    expect = case["expect"]
    fix_text = case["fix_text"]
    results = await search(tenant.org_id, tenant.equipment_id, fix_text)
    manual = [r.text for r in results if r.source_type == "manual"]
    report = await prescreen(fix_text, manual)
    reasons: list[str] = []

    if report.get("error"):
        reasons.append(f"prescreen failed: {report['error']}")
        return reasons

    flags = report.get("hazard_flags", [])
    if "min_hazard_flags" in expect and len(flags) < expect["min_hazard_flags"]:
        reasons.append(f"{len(flags)} hazard flags < {expect['min_hazard_flags']}")
    if "overall_risk_at_least" in expect:
        want = RISK_ORDER[expect["overall_risk_at_least"]]
        got = RISK_ORDER.get(report.get("overall_risk", "low"), 0)
        if got < want:
            reasons.append(
                f"overall_risk={report.get('overall_risk')!r} < {expect['overall_risk_at_least']!r}"
            )
    return reasons


async def evaluate_case(tenant: DemoTenant, case: dict) -> list[str]:
    """Dispatch a case to the right evaluator by its ``kind``."""
    if case["kind"] == "answer":
        return await _eval_answer_case(tenant, case)
    if case["kind"] == "prescreen":
        return await _eval_prescreen_case(tenant, case)
    return [f"unknown case kind {case['kind']!r}"]


async def collect_baseline(tenant: DemoTenant, questions: list[str]) -> list[dict]:
    """Record the current retrieval results per question, to compare against later."""
    rows = []
    for q in questions:
        chunks = await search(tenant.org_id, tenant.equipment_id, q)
        rows.append(
            {
                "question": q,
                "retrieved_chunk_ids": [str(c.chunk_id) for c in chunks],
                "top_source_types": [c.source_type for c in chunks],
            }
        )
    return rows


def _write_baseline(rows: list[dict]) -> None:
    """Persist baseline rows as JSON Lines to ``baseline.jsonl``."""
    BASELINE_PATH.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


async def report_drift(tenant: DemoTenant) -> None:
    """Report retrieval drift against the recorded baseline (informational).

    Drift is never a release gate here: re-ingesting the demo manual legitimately
    changes chunk ids. The signal is *how much* of the baseline retrieval set
    still appears — a sudden drop flags a retrieval regression worth a look. Per
    CLAUDE.md §8.4 baselines are per-backend; never compare across backends.
    """
    lines = [ln for ln in BASELINE_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        return
    print("\nRegression drift vs baseline (informational):")
    for ln in lines:
        rec = json.loads(ln)
        chunks = await search(tenant.org_id, tenant.equipment_id, rec["question"])
        now = [str(c.chunk_id) for c in chunks]
        base = rec["retrieved_chunk_ids"]
        kept = len(set(base) & set(now))
        denom = len(base) or 1
        print(f"  [{kept}/{len(base)} kept] {rec['question']}")
        if kept < denom:
            print(f"      baseline source_types={rec['top_source_types']}")
            print(f"      current  source_types={[c.source_type for c in chunks]}")


async def run_evals(record_baseline: bool = False) -> int:
    """Build the eval tenant, run all cases, print results, and return an exit code.

    With ``record_baseline`` it instead records the current retrieval as the new
    baseline. Returns 0 if every case passed, 1 otherwise.
    """
    cases = load_cases()
    print(f"Building eval tenant {EVAL_ORG!r} (ingest manual + approve field fix)...")
    tenant = await build_demo_tenant(EVAL_ORG)

    results: list[tuple[str, str, bool, list[str]]] = []
    for case in cases:
        reasons = await evaluate_case(tenant, case)
        results.append((case["id"], case["kind"], not reasons, reasons))

    width = max(len(cid) for cid, *_ in results)
    print("\nSafety eval results:")
    for cid, kind, passed, reasons in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {cid.ljust(width)}  ({kind})")
        for r in reasons:
            print(f"           - {r}")

    questions = [c["question"] for c in cases if c["kind"] == "answer"]
    if record_baseline:
        rows = await collect_baseline(tenant, questions)
        _write_baseline(rows)
        print(f"\nRecorded regression baseline ({len(rows)} questions) -> {BASELINE_PATH.name}")
    elif BASELINE_PATH.exists() and BASELINE_PATH.read_text(encoding="utf-8").strip():
        await report_drift(tenant)

    failed = [cid for cid, _, passed, _ in results if not passed]
    total = len(results)
    print(f"\n{total - len(failed)}/{total} cases passed.")
    if failed:
        print("FAILED:", ", ".join(failed))
    return 1 if failed else 0


def main() -> None:
    """Parse CLI args and run the eval suite, exiting with its status code."""
    parser = argparse.ArgumentParser(description="Run FixMate safety + regression evals.")
    parser.add_argument(
        "--record-baseline",
        action="store_true",
        help="record the current retrieval as the regression baseline and exit 0",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(run_evals(record_baseline=args.record_baseline)))


if __name__ == "__main__":
    main()
