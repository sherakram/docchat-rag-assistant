from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from backend.config import TOP_K


class ChunkPreview(BaseModel):
    chunk_index: int
    page: int
    word_count: int
    text: str


class UploadResponse(BaseModel):
    doc_id: str
    filename: str
    page_count: int
    pages_with_text: int
    chunk_count: int
    preview_page: int
    preview: str
    sample_chunks: list[ChunkPreview]


class SearchRequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    doc_id: str | None = None
    top_k: int = Field(default=TOP_K, ge=1, le=10)


class SearchHit(BaseModel):
    doc_id: str
    filename: str
    page: int
    chunk_index: int
    similarity: float
    above_threshold: bool
    text: str


class SearchResponse(BaseModel):
    question: str
    supported: bool
    best_similarity: float | None
    threshold: float
    results: list[SearchHit]