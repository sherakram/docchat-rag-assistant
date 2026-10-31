import time

from google import genai
from google.genai import errors, types

from backend.config import (
    EMBED_BATCH_SIZE,
    EMBEDDING_DIMENSIONS,
    GEMINI_API_KEY,
    GEMINI_EMBEDDING_MODEL,
)


class EmbeddingError(Exception):
    """Embeddings nahi ban sake (key, limit ya network ka masla)."""


_client = None


def _get_client() -> genai.Client:
    """Client ek hi baar banta hai aur dobara use hota hai."""
    global _client
    if _client is None:
        if not GEMINI_API_KEY or GEMINI_API_KEY == "your-key-here":
            raise EmbeddingError("GEMINI_API_KEY is not set. Add it to your .env file.")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def embed_texts(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """Texts ki list lo, har text ke liye ek embedding (floats ki list) wapas karo."""
    client = _get_client()
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        vectors.extend(_embed_batch(client, batch, task_type))
    return vectors


def _embed_batch(client: genai.Client, batch: list[str], task_type: str) -> list[list[float]]:
    for attempt in range(3):
        try:
            response = client.models.embed_content(
                model=GEMINI_EMBEDDING_MODEL,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=EMBEDDING_DIMENSIONS,
                ),
            )
            return [item.values for item in response.embeddings]
        except errors.APIError as exc:
            # 429 = limit, 500/503 = Google ka masla: thora ruk kar dobara koshish
            if exc.code in (429, 500, 503) and attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            if exc.code in (400, 401, 403):
                raise EmbeddingError(
                    f"Gemini rejected the request (code {exc.code}). "
                    "Check that your API key is valid and the model name is correct."
                ) from exc
            if exc.code == 429:
                raise EmbeddingError(
                    "Gemini rate limit reached. Wait a minute and try again."
                ) from exc
            raise EmbeddingError(f"Gemini API error (code {exc.code}).") from exc
    raise EmbeddingError("Embedding request failed.")