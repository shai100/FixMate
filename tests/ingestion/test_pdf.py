from pathlib import Path

import pytest

from fixmate.ingestion.pdf import extract_figures, extract_pages

# A real OEM-style manual whose figures use print colorspaces (DeviceCMYK and
# single-channel Separation/spot colors). These previously crashed figure
# extraction because PNG encoding only supports gray/RGB — this fixture guards
# the colorspace-normalization fix in extract_figures.
_CMYK_MANUAL = Path(__file__).parent.parent / "fixtures" / "sample-manual 02.pdf"


def test_extract_pages_returns_text_with_page_numbers(sample_pdf):
    pages = extract_pages(sample_pdf)
    assert [p for p, _ in pages] == [1, 2, 3]
    assert "E47" in dict(pages)[2]


def test_extract_figures_finds_one_figure_with_page_and_bbox(sample_pdf):
    figures = extract_figures(sample_pdf)
    assert len(figures) == 1
    fig = figures[0]
    assert fig.page == 2
    assert fig.image  # non-empty bytes
    assert set(fig.bbox) == {"x0", "y0", "x1", "y1"}


@pytest.mark.skipif(not _CMYK_MANUAL.exists(), reason="CMYK fixture manual not present")
def test_extract_figures_handles_cmyk_and_separation_colorspaces():
    """Regression: figures in DeviceCMYK / Separation colorspaces must not crash.

    PNG only supports gray and RGB, so PyMuPDF rejects CMYK and single-channel
    spot-color pixmaps unless they are converted to RGB first. Every figure must
    come back as non-empty PNG bytes rather than raising ``FzErrorArgument``.
    """
    figures = extract_figures(_CMYK_MANUAL)
    assert figures, "expected the manual to contain embedded figures"
    for fig in figures:
        assert fig.image, "every figure must encode to non-empty PNG bytes"
        assert fig.media_type == "image/png"
