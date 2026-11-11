import chromadb

from backend.config import CHROMA_DIR, COLLECTION_NAME

_client = None


def _collection():
    global _client
    if _client is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        # PersistentClient = data disk par save hota hai, server band hone par bhi rehta hai
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},  # cosine similarity se naapo
    )


def add_chunks(
    doc_id: str,
    filename: str,
    chunks: list[dict],
    embeddings: list[list[float]],
    content_hash: str,
    page_count: int,
    uploaded_at: str,
) -> None:
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
                "content_hash": content_hash,
                "page_count": page_count,
                "uploaded_at": uploaded_at,
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


def find_doc_by_hash(content_hash: str) -> dict | None:
    """Agar yehi PDF pehle upload ho chuki hai to uska doc_id aur filename do."""
    result = _collection().get(
        where={"content_hash": content_hash}, limit=1, include=["metadatas"]
    )
    if result["ids"]:
        meta = result["metadatas"][0]
        return {"doc_id": meta["doc_id"], "filename": meta["filename"]}
    return None


def list_documents() -> list[dict]:
    """Sab documents, naye pehle. Chunks ke metadata ko doc_id ke hisaab se jama karta hai."""
    metadatas = _collection().get(include=["metadatas"])["metadatas"]

    docs: dict[str, dict] = {}
    for meta in metadatas:
        doc = docs.setdefault(
            meta["doc_id"],
            {
                "doc_id": meta["doc_id"],
                "filename": meta["filename"],
                "chunk_count": 0,
                "page_count": 0,
                # purani uploads mein ye keys nahi hotin
                "uploaded_at": meta.get("uploaded_at", ""),
            },
        )
        doc["chunk_count"] += 1
        doc["page_count"] = max(
            doc["page_count"], int(meta.get("page_count", 0)), int(meta["page"])
        )

    return sorted(docs.values(), key=lambda d: d["uploaded_at"], reverse=True)


def peek(limit: int = 3) -> dict:
    """Debugging ke liye: database ke pehle kuch records."""
    return _collection().get(limit=limit, include=["documents", "metadatas"])


def search(query_embedding: list[float], top_k: int = 4, doc_id: str | None = None) -> list[dict]:
    """Sab se qareebi chunks wapas karo (sab se milta julta pehle).

    doc_id dene par sirf usi document mein dhoondhta hai.
    """
    collection = _collection()
    if collection.count() == 0:
        return []

    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"doc_id": doc_id} if doc_id else None,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for text, meta, distance in zip(
        result["documents"][0], result["metadatas"][0], result["distances"][0]
    ):
        hits.append(
            {
                "text": text,
                "doc_id": meta["doc_id"],
                "filename": meta["filename"],
                "page": meta["page"],
                "chunk_index": meta["chunk_index"],
                "similarity": round(1 - distance, 4),
            }
        )
    return hits