"""Splits page text into overlapping chunks suitable for embedding and retrieval.

Why chunk at all? Embeddings work best on focused passages, and the reranker is
stable only below ~512 tokens. So each page's text is broken into pieces of at
most ``max_chars`` characters, split on sentence boundaries where possible, with
a small ``overlap`` carried between consecutive chunks so a fact split across a
boundary is still findable. Character count is used as a cheap stand-in for token
count to avoid a tokenizer dependency in this hot path.
"""

import re
from dataclasses import dataclass

# Split on sentence terminators (keep the terminator with the sentence). Chunks
# are assembled up to a char budget rather than a token budget: char count is a
# cheap proxy for the <512-token reranker stability constraint (CLAUDE.md §4.4),
# avoiding a tokenizer dependency in the ingestion hot path.
_SENTENCE = re.compile(r"\S.*?(?:[.!?](?=\s|$)|\n+|$)", re.DOTALL)


@dataclass
class TextChunk:
    """A retrieval-sized slice of text and the page it came from."""

    page: int
    text: str


def _split_sentences(text: str) -> list[str]:
    """Break text into trimmed sentences, keeping each terminator with its sentence."""
    return [m.group().strip() for m in _SENTENCE.finditer(text) if m.group().strip()]


def chunk_pages(
    pages: list[tuple[int, str]], max_chars: int = 800, overlap: int = 120
) -> list[TextChunk]:
    """Turn extracted pages into overlapping ``TextChunk``s, one stream per page.

    Greedily packs whole sentences up to ``max_chars``; when a chunk fills, it
    starts the next one with the last ``overlap`` characters for continuity. A
    single sentence longer than the budget is hard-split.
    """
    chunks: list[TextChunk] = []
    for page, text in pages:
        sentences = _split_sentences(text)
        current = ""
        for sentence in sentences:
            candidate = f"{current} {sentence}".strip() if current else sentence
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                chunks.append(TextChunk(page=page, text=current))
                tail = current[-overlap:] if overlap else ""
                current = f"{tail} {sentence}".strip()
            else:
                # A single sentence longer than the budget: hard-split it.
                current = sentence
            while len(current) > max_chars:
                chunks.append(TextChunk(page=page, text=current[:max_chars]))
                current = current[max_chars - overlap :] if overlap else current[max_chars:]
        if current:
            chunks.append(TextChunk(page=page, text=current))
    return chunks
