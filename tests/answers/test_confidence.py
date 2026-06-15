from fixmate.answers.confidence import confidence_band


def test_high_band():
    assert confidence_band(0.70) == "high"
    assert confidence_band(0.91) == "high"


def test_medium_band():
    assert confidence_band(0.45) == "medium"
    assert confidence_band(0.69) == "medium"


def test_low_band():
    assert confidence_band(0.44) == "low"
    assert confidence_band(0.0) == "low"


def test_no_results_is_low():
    assert confidence_band(None) == "low"
