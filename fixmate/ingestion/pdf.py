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

    Normalizes non-RGB/gray images to RGB before PNG encoding, since PNG (and
    therefore PyMuPDF's ``tobytes("png")``) only supports DeviceGray and
    DeviceRGB. PDF manuals routinely embed print-oriented colorspaces —
    DeviceCMYK and single-channel Separation/spot-color images — which must be
    converted first or encoding raises an ``FzErrorArgument``.
    """
    figures: list[ExtractedFigure] = []
    with fitz.open(path) as doc:
        for i, page in enumerate(doc):
            for img in page.get_images(full=True):
                xref = img[0]
                rects = page.get_image_rects(xref)
                rect = rects[0] if rects else page.rect
                pix = fitz.Pixmap(doc, xref)
                # Convert anything that isn't already plain gray/RGB to RGB before
                # PNG encoding. A channel-count check (n >= 4) is not enough:
                # single-channel Separation/spot colorspaces have n == 1 yet are
                # still rejected by the PNG encoder, so key on the colorspace name.
                cs = pix.colorspace
                if cs is None or cs.name not in ("DeviceGray", "DeviceRGB"):
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                figures.append(
                    ExtractedFigure(
                        page=i + 1,
                        bbox={"x0": rect.x0, "y0": rect.y0, "x1": rect.x1, "y1": rect.y1},
                        image=pix.tobytes("png"),
                    )
                )
    return figures
