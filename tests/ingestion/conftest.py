import fitz
import pytest

PAGE_TEXT = {
    1: "Maintenance manual. This pump moves dialysate concentrate through the circuit.",
    2: "Error E47: concentrate valve blocked. Inspect the valve seat for scale buildup.",
    3: "Reassembly. Tighten to 12 Nm. Do not exceed torque or the housing will crack.",
}


@pytest.fixture(scope="session")
def sample_pdf(tmp_path_factory):
    """A 3-page manual with known sentences and one embedded image on page 2."""
    path = tmp_path_factory.mktemp("fixtures") / "sample-manual.pdf"
    doc = fitz.open()
    for page_no in (1, 2, 3):
        page = doc.new_page()
        page.insert_text((72, 72), PAGE_TEXT[page_no], fontsize=12)
        if page_no == 2:
            pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 64, 64))
            pix.set_rect(pix.irect, (200, 40, 40))  # solid red square
            page.insert_image(fitz.Rect(72, 120, 200, 248), pixmap=pix)
    doc.save(path)
    doc.close()
    return path
