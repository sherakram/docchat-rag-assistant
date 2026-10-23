import pymupdf


class PDFError(Exception):
    """Ye PDF padhi nahi ja saki (kharab file, password, wagera)."""


def extract_pages(data: bytes) -> list[dict]:
    """PDF ke bytes lo, aur har page ke liye {"page": number, "text": text} wapas karo.

    Page numbers 1 se shuru hote hain (jaise PDF viewer mein dikhte hain).
    """
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise PDFError("Could not read this file as a PDF.") from exc

    with doc:
        if doc.needs_pass:
            raise PDFError("Password-protected PDFs are not supported.")

        pages = []
        for number, page in enumerate(doc, start=1):
            pages.append({"page": number, "text": page.get_text().strip()})

    return pages