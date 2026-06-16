import uuid

from fixmate.answers.composer import _resolve_citations

FULL_A = "0eca1ad9-44a9-43ed-a721-51a73af526c1"
FULL_B = "a9c21a77-146e-463d-a415-c9a25511a34f"


def _by_id(*ids: str) -> dict[str, object]:
    return {i: object() for i in ids}


def test_full_uuid_citation_resolves():
    valid, invalid = _resolve_citations(f"do X [chunk:{FULL_A}]", _by_id(FULL_A, FULL_B))
    assert valid == [FULL_A] and invalid == []


def test_abbreviated_prefix_resolves_to_full_id():
    # qwen3:4b cites only the leading segment — must still ground.
    valid, invalid = _resolve_citations("do X [chunk:0eca1ad9].", _by_id(FULL_A, FULL_B))
    assert valid == [FULL_A] and invalid == []


def test_unknown_token_is_invalid():
    valid, invalid = _resolve_citations("see [chunk:deadbeef]", _by_id(FULL_A, FULL_B))
    assert valid == [] and invalid == ["deadbeef"]


def test_ambiguous_prefix_is_invalid():
    a = "abcd0000-0000-0000-0000-000000000000"
    b = "abcd1111-1111-1111-1111-111111111111"
    valid, invalid = _resolve_citations("see [chunk:abcd]", _by_id(a, b))
    assert valid == [] and invalid == ["abcd"]


def test_dedupes_full_and_prefix_of_same_id():
    valid, invalid = _resolve_citations(
        f"[chunk:0eca1ad9] and [chunk:{FULL_A}]", _by_id(FULL_A, FULL_B)
    )
    assert valid == [FULL_A] and invalid == []


def test_uppercase_token_resolves_case_insensitively():
    upper = str(uuid.UUID(FULL_A)).upper()
    valid, _ = _resolve_citations(f"[chunk:{upper}]", _by_id(FULL_A))
    assert valid == [FULL_A]
