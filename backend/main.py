import hashlib
import re
import uuid
from datetime import datetime, timezone
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
from backend.schemas import (
    ChatRequest,
    ChatResponse,
    ChunkPreview,
    DeleteResponse,
    DocumentListResponse,
    SearchRequest,
    SearchResponse,
    UploadResponse,
)
from backend.services.chat import answer_question
from backend.services.chunker import chunk_pages
from backend.services.embeddings import EmbeddingError, embed_texts
from backend.services.llm import LLMError
from backend.services.pdf_loader import PDFError, extract_pages
from backend.services.retriever import retrieve
from backend.services.vector_store import (
    add_chunks,
    count_for_doc,
    delete_doc,
    find_doc_by_hash,
    list_documents,
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DOC_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")

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

    # 4. Duplicate check: wohi file pehle upload ho chuki hai? (embeddings se pehle, kharcha bachta hai)
    content_hash = hashlib.sha256(data).hexdigest()
    existing = find_doc_by_hash(content_hash)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"This PDF is already uploaded ({existing['filename']}).",
        )

    # 5. Text nikalo
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

    # 6. Chunks banao
    chunks = chunk_pages(pages, CHUNK_SIZE_WORDS, CHUNK_OVERLAP_WORDS)
    if not chunks:
        raise HTTPException(
            status_code=422,
            detail="This PDF has too little text to index.",
        )

    # 7. Embeddings banao (Gemini). Fail hui to kuch bhi save nahi hota.
    doc_id = uuid.uuid4().hex
    try:
        vectors = embed_texts([c["text"] for c in chunks])
    except EmbeddingError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    # 8. Vector database mein rakho
    add_chunks(
        doc_id,
        original_name,
        chunks,
        vectors,
        content_hash=content_hash,
        page_count=len(pages),
        uploaded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )

    # 9. Asli PDF bhi save karo (apne random id se, user ke diye naam se nahi)
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


@app.get("/api/documents", response_model=DocumentListResponse)
def get_documents():
    """Sab uploaded documents (naye pehle)."""
    return {"documents": list_documents()}


@app.delete("/api/documents/{doc_id}", response_model=DeleteResponse)
def remove_document(doc_id: str):
    """Document ke chunks aur uski PDF file dono hata do."""
    # Pehle format check: sirf apni banayi hui id (32 hex) file path tak pohanch sakti hai
    if not DOC_ID_PATTERN.fullmatch(doc_id):
        raise HTTPException(status_code=400, detail="Invalid document id.")
    if count_for_doc(doc_id) == 0:
        raise HTTPException(status_code=404, detail="Document not found.")

    delete_doc(doc_id)
    (UPLOAD_DIR / f"{doc_id}.pdf").unlink(missing_ok=True)
    return {"deleted": doc_id}


@app.post("/api/search", response_model=SearchResponse)
def search_documents(request: SearchRequest):
    """Sawal ke liye qareebi chunks dhoondo (sirf retrieval, LLM nahi)."""
    if request.doc_id and count_for_doc(request.doc_id) == 0:
        raise HTTPException(status_code=404, detail="That document no longer exists.")
    try:
        return retrieve(request.question, request.top_k, request.doc_id)
    except EmbeddingError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Sawal ka jawab documents ke andar se, page citations ke saath."""
    if request.doc_id and count_for_doc(request.doc_id) == 0:
        raise HTTPException(status_code=404, detail="That document no longer exists.")
    try:
        return answer_question(request.question, request.doc_id)
    except (EmbeddingError, LLMError) as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# Ye line SABSE AKHIR mein rahe
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")