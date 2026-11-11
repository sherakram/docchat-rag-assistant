import hashlib
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import (
    CHAT_RATE_LIMIT,
    CHUNK_OVERLAP_WORDS,
    CHUNK_SIZE_WORDS,
    GEMINI_API_KEY,
    MAX_CHUNKS_PER_DOC,
    MAX_PDF_PAGES,
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_MB,
    RATE_LIMIT_WINDOW_SECONDS,
    UPLOAD_DIR,
    UPLOAD_RATE_LIMIT,
)
from backend.ratelimit import RateLimiter
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("docchat")

if not GEMINI_API_KEY or GEMINI_API_KEY == "your-key-here":
    logger.warning("GEMINI_API_KEY is not set: uploads and chat will fail until you add it to .env")

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DOC_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")

# Content-Security-Policy: sirf apni files aur Google Fonts ki ijazat
CSP = (
    "default-src 'self'; script-src 'self'; "
    "style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
    "img-src 'self' data:; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)

upload_limiter = RateLimiter(UPLOAD_RATE_LIMIT, RATE_LIMIT_WINDOW_SECONDS)
chat_limiter = RateLimiter(CHAT_RATE_LIMIT, RATE_LIMIT_WINDOW_SECONDS)

app = FastAPI(title="Chat with Your Documents")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    # /docs (Swagger) apni scripts CDN se laata hai, is liye us par CSP nahi lagate
    if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
        response.headers["Content-Security-Policy"] = CSP
    return response


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    """Koi anjaan error: andar ki tafseel sirf log mein, user ko saaf aam message."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


@app.get("/api/health")
def health():
    """Chhota sa check: kya server zinda hai?"""
    return {"status": "ok"}


@app.post(
    "/api/upload",
    response_model=UploadResponse,
    dependencies=[Depends(upload_limiter)],
)
def upload_pdf(file: UploadFile = File(...)):
    started = time.perf_counter()
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

    # 4. Duplicate check (embeddings se pehle, kharcha bachta hai)
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

    if len(pages) > MAX_PDF_PAGES:
        raise HTTPException(
            status_code=413, detail=f"This PDF has too many pages (max {MAX_PDF_PAGES})."
        )

    pages_with_text = sum(1 for p in pages if p["text"])
    if pages_with_text == 0:
        raise HTTPException(
            status_code=422,
            detail="No extractable text found. Scanned PDFs need OCR, which is not supported yet.",
        )

    # 6. Chunks banao
    chunks = chunk_pages(pages, CHUNK_SIZE_WORDS, CHUNK_OVERLAP_WORDS)
    if not chunks:
        raise HTTPException(status_code=422, detail="This PDF has too little text to index.")
    if len(chunks) > MAX_CHUNKS_PER_DOC:
        raise HTTPException(
            status_code=413, detail="This PDF is too large to index. Try a smaller document."
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

    logger.info(
        "Indexed doc_id=%s pages=%d chunks=%d in %.1fs",
        doc_id, len(pages), len(chunks), time.perf_counter() - started,
    )

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
    # Sirf apni banayi hui id (32 hex) file path tak pohanch sakti hai
    if not DOC_ID_PATTERN.fullmatch(doc_id):
        raise HTTPException(status_code=400, detail="Invalid document id.")
    if count_for_doc(doc_id) == 0:
        raise HTTPException(status_code=404, detail="Document not found.")

    delete_doc(doc_id)
    (UPLOAD_DIR / f"{doc_id}.pdf").unlink(missing_ok=True)
    logger.info("Deleted doc_id=%s", doc_id)
    return {"deleted": doc_id}


@app.post(
    "/api/search",
    response_model=SearchResponse,
    dependencies=[Depends(chat_limiter)],
)
def search_documents(request: SearchRequest):
    """Sawal ke liye qareebi chunks dhoondo (sirf retrieval, LLM nahi)."""
    if request.doc_id and count_for_doc(request.doc_id) == 0:
        raise HTTPException(status_code=404, detail="That document no longer exists.")
    try:
        return retrieve(request.question, request.top_k, request.doc_id)
    except EmbeddingError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post(
    "/api/chat",
    response_model=ChatResponse,
    dependencies=[Depends(chat_limiter)],
)
def chat(request: ChatRequest):
    """Sawal ka jawab documents ke andar se, page citations ke saath."""
    started = time.perf_counter()
    if request.doc_id and count_for_doc(request.doc_id) == 0:
        raise HTTPException(status_code=404, detail="That document no longer exists.")
    try:
        result = answer_question(request.question, request.doc_id)
    except (EmbeddingError, LLMError) as exc:
        logger.warning("Chat failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))

    # Privacy: sawal ka text log nahi karte, sirf natija
    logger.info(
        "Chat supported=%s best_similarity=%s sources=%d in %.1fs",
        result["supported"], result["best_similarity"], len(result["sources"]),
        time.perf_counter() - started,
    )
    return result


# Ye line SABSE AKHIR mein rahe
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")