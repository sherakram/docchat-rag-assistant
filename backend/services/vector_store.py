import chromadb

from backend.config import CHROMA_DIR, COLLECTION_NAME

_client = None


def _collection():
    global _client
    if _client is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def add_chunks(doc_id: str, filename: str, chunks: list[dict], embeddings: list[list[float]]) -> None:
    _collection().add(
        ids=[f"{doc_id}_{c['chunk_index']}" for c in chunks],
        embeddings=embeddings,
        documents=[c["text"] for c in chunks],
        metadatas=[
            {
                "doc_id": doc_id,
                "filename": filename,
                "page": c["page"],
                "chunk_index": c["chunk_index"],
            }
            for c in chunks
        ],
    )


def total_count() -> int:
    return _collection().count()


def count_for_doc(doc_id: str) -> int:
    return len(_collection().get(where={"doc_id": doc_id}, include=[])["ids"])


def delete_doc(doc_id: str) -> None:
    _collection().delete(where={"doc_id": doc_id})


def peek(limit: int = 3) -> dict:
    """Debugging ke liye: database ke pehle kuch records."""
    return _collection().get(limit=limit, include=["documents", "metadatas"])