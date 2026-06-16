"""Low-level PDF extraction using PyMuPDF (imported as ``fitz``).

Two pure functions that read a PDF off disk: ``extract_pages`` pulls the plain
text per page, and ``extract_figures`` pulls embedded images with their page and
bounding box. The rest of the pipeline turns these into searchable chunks and
captioned figures.
"""

from dataclasses import dataclass
from pathlib import Path

import fitz


@dataclass
class ExtractedFigure:
    """One image pulled from a PDF: its page (1-based), bounding box, and PNG bytes."""

    page: int  # 1-based
    bbox: dict  # {"x0","y0","x1","y1"} in PDF points
    image: bytes  # PNG bytes
    media_type: str = "image/png"


def extract_pages(path: str | Path) -> list[tuple[int, str]]:
    """Return ``(page_number, text)`` for each page, page numbers starting at 1."""
    with fitz.open(path) as doc:
        return [(i + 1, page.get_text()) for i, page in enumerate(doc)]


def extract_figures(path: str | Path) -> list[ExtractedFigure]:
    """Extract every embedded image as an ``ExtractedFigure`` (PNG-encoded).

    Normalizes CMYK/alpha images to RGB before PNG encoding, since PyMuPDF can't
    encode >4-channel colorspaces directly.
    """
    figures: list[ExtractedFigure] = []
    with fitz.open(path) as doc:
        for i, page in enumerate(doc):
            for img in page.get_images(full=True):
                xref = img[0]
                rects = page.get_image_rects(xref)
                rect = rects[0] if rects else page.rect
                pix = fitz.Pixmap(doc, xref)
                # Normalize CMYK / alpha-bearing pixmaps to plain RGB before PNG
                # encoding; tobytes() rejects >4 channel colorspaces.
                if pix.n - pix.alpha >= 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                figures.append(
                    ExtractedFigure(
                        page=i + 1,
                        bbox={"x0": rect.x0, "y0": rect.y0, "x1": rect.x1, "y1": rect.y1},
                        image=pix.tobytes("png"),
                    )
                )
    return figures
