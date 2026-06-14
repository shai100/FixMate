import uuid

from fixmate.core import storage
from fixmate.ingestion.pdf import ExtractedFigure
from fixmate.llm.base import LLMProvider

_EXT = {"image/png": "png", "image/jpeg": "jpg"}


async def caption_and_store(
    provider: LLMProvider,
    figure: ExtractedFigure,
    org_id: uuid.UUID,
    document_id: uuid.UUID,
    context: str,
) -> dict:
    try:
        caption = await provider.caption_image(figure.image, figure.media_type, context)
    except NotImplementedError:
        # Local backend (qwen3:4b) has no vision (spec §8.3); fall back to a
        # deterministic, non-empty caption so the figure stays indexable.
        caption = f"Figure on page {figure.page} of {context}"

    ext = _EXT.get(figure.media_type, "png")
    key_suffix = f"figures/{document_id}/p{figure.page}-{uuid.uuid4().hex[:8]}.{ext}"
    storage_key = storage.put_object(org_id, key_suffix, figure.image, figure.media_type)

    return {
        "page": figure.page,
        "caption": caption,
        "storage_key": storage_key,
        "bbox": figure.bbox,
    }
