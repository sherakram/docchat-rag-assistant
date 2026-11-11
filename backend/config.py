import os
from pathlib import Path

from dotenv import load_dotenv

# .env file ko read karke uski values ko environment variables bana deta hai
load_dotenv()


def _number(name: str, default, cast=int):
    """Number wali setting .env se padho; ghalat likha ho to saaf error do."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return cast(raw)
    except ValueError:
        raise RuntimeError(f"{name} in .env must be a number, got: {raw!r}") from None


# --- Gemini ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-3.5-flash-lite")
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIMENSIONS = 768  # badla to purani PDFs dobara index karni parengi
EMBED_BATCH_SIZE = 50
LLM_TIMEOUT_SECONDS = 60

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
CHROMA_DIR = BASE_DIR / "data" / "chroma"
COLLECTION_NAME = "documents"

# --- Upload limits ---
MAX_UPLOAD_MB = _number("MAX_UPLOAD_MB", 10)
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MAX_PDF_PAGES = _number("MAX_PDF_PAGES", 200)
MAX_CHUNKS_PER_DOC = _number("MAX_CHUNKS_PER_DOC", 1000)

# --- Chunking (words mein). Badalne ke baad PDFs dobara upload karni parengi ---
CHUNK_SIZE_WORDS = _number("CHUNK_SIZE_WORDS", 200)
CHUNK_OVERLAP_WORDS = _number("CHUNK_OVERLAP_WORDS", 40)

# --- Retrieval ---
TOP_K = _number("TOP_K", 4)
MIN_SIMILARITY = _number("MIN_SIMILARITY", 0.5, float)

# --- Rate limiting (har client IP ke liye, ek window mein) ---
RATE_LIMIT_WINDOW_SECONDS = 60
CHAT_RATE_LIMIT = _number("CHAT_RATE_LIMIT", 20)
UPLOAD_RATE_LIMIT = _number("UPLOAD_RATE_LIMIT", 5)