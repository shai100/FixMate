from fixmate.retrieval.fusion import apply_field_fix_boost, reciprocal_rank_fusion


def test_rrf_rewards_agreement():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "a", "d"]])
    assert fused[0] in ("a", "b") and set(fused) == {"a", "b", "c", "d"}


def test_rrf_returns_scores_when_requested():
    scores = reciprocal_rank_fusion([["a", "b"], ["a", "c"]], with_scores=True)
    assert scores["a"] > scores["b"]
    assert set(scores) == {"a", "b", "c"}


def test_field_fix_boost_promotes_fix():
    scores = {"manual1": 0.030, "fix1": 0.029}
    boosted = apply_field_fix_boost(scores, field_fix_ids={"fix1"}, boost=1.15)
    assert boosted["fix1"] > boosted["manual1"]
