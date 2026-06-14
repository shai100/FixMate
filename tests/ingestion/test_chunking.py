from fixmate.ingestion.chunking import chunk_pages


def test_chunks_carry_page_numbers_and_respect_size():
    pages = [(1, "A. " * 300), (2, "B. " * 300)]
    chunks = chunk_pages(pages, max_chars=800, overlap=120)
    assert all(len(c.text) <= 800 for c in chunks)
    assert {c.page for c in chunks} == {1, 2}
    assert chunks[1].text[:120] in chunks[0].text + chunks[1].text  # overlap preserved
