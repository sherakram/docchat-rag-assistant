from pydantic import BaseModel


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