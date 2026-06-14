import re
from dataclasses import dataclass

# Split on sentence terminators (keep the terminator with the sentence). Chunks
# are assembled up to a char budget rather than a token budget: char count is a
# cheap proxy for the <512-token reranker stability constraint (CLAUDE.md §4.4),
# avoiding a tokenizer dependency in the ingestion hot path.
_SENTENCE = re.compile(r"\S.*?(?:[.!?](?=\s|$)|\n+|$)", re.DOTALL)


@dataclass
class TextChunk:
    page: int
    text: str


def _split_sentences(text: str) -> list[str]:
    return [m.group().strip() for m in _SENTENCE.finditer(text) if m.group().strip()]


def chunk_pages(
    pages: list[tuple[int, str]], max_chars: int = 800, overlap: int = 120
) -> list[TextChunk]:
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
