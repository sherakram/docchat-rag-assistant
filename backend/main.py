import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

from backend.config import (
    CHUNK_OVERLAP_WORDS,
    CHUNK_SIZE_WORDS,
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_MB,
    UPLOAD_DIR,
)
from backend.schemas import ChunkPreview, UploadResponse
from backend.services.chunker import chunk_pages
from backend.services.pdf_loader import PDFError, extract_pages

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="Chat with Your Documents")


@app.get("/api/health")
def health():
    """Chhota sa check: kya server zinda hai?"""
    return {"status": "ok"}


@app.post("/api/upload", response_model=UploadResponse)
def upload_pdf(file: UploadFile = File(...)):
    original_name = file.filename or "document.pdf"

    # 1. Extension check
    if not original_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only .pdf files are allowed.")

    # 2. Size check
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413, detail=f"File is too large (max {MAX_UPLOAD_MB} MB)."
        )

    # 3. Magic bytes check: asli PDF hamesha %PDF se shuru hoti hai
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="This is not a valid PDF file.")

    # 4. Text nikalo
    try:
        pages = extract_pages(data)
    except PDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    pages_with_text = sum(1 for p in pages if p["text"])
    if pages_with_text == 0:
        raise HTTPException(
            status_code=422,
            detail="No extractable text found. Scanned PDFs need OCR, which is not supported yet.",
        )

    # 5. Chunks banao
    chunks = chunk_pages(pages, CHUNK_SIZE_WORDS, CHUNK_OVERLAP_WORDS)
    if not chunks:
        raise HTTPException(
            status_code=422,
            detail="This PDF has too little text to index.",
        )

    # 6. Sab theek: file save karo (user ke diye naam se nahi, apne random id se)
    doc_id = uuid.uuid4().hex
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / f"{doc_id}.pdf").write_bytes(data)

    first = next(p for p in pages if p["text"])
    return UploadResponse(
        doc_id=doc_id,
        filename=original_name,
        page_count=len(pages),
        pages_with_text=pages_with_text,
        chunk_count=len(chunks),
        preview_page=first["page"],
        preview=first["text"][:300],
        sample_chunks=[
            ChunkPreview(
                chunk_index=c["chunk_index"],
                page=c["page"],
                word_count=len(c["text"].split()),
                text=c["text"][:200],
            )
            for c in chunks[:3]
        ],
    )


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")