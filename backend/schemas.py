from pydantic import BaseModel


class UploadResponse(BaseModel):
    doc_id: str
    filename: str
    page_count: int
    pages_with_text: int
    preview_page: int
    preview: str