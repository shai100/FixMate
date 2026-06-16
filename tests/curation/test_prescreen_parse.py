from fixmate.curation.prescreen import _parse_report

OBJ = '{"hazard_flags": ["pressure"], "overall_risk": "high"}'


def test_plain_json_parses():
    assert _parse_report(OBJ) == {"hazard_flags": ["pressure"], "overall_risk": "high"}


def test_json_wrapped_in_stray_tokens_is_recovered():
    assert _parse_report(f"Here is the advisory:\n{OBJ}\nDone.") == {
        "hazard_flags": ["pressure"],
        "overall_risk": "high",
    }


def test_truncated_json_returns_none():
    assert _parse_report('{"hazard_flags": ["pressure"], "overall_ri') is None


def test_non_object_json_returns_none():
    assert _parse_report('["pressure"]') is None


def test_empty_returns_none():
    assert _parse_report("") is None
