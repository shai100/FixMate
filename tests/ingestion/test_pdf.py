from fixmate.ingestion.pdf import extract_figures, extract_pages


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
