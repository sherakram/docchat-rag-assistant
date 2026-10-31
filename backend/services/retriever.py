from backend.config import MIN_SIMILARITY, TOP_K
from backend.services.embeddings import embed_texts
from backend.services.vector_store import search


def retrieve(question: str, top_k: int = TOP_K, doc_id: str | None = None) -> dict:
    """Sawal ke liye qareebi chunks dhoondo aur batao ke jawab documents mein 'supported' hai ya nahi."""
    query_vector = embed_texts([question], task_type="RETRIEVAL_QUERY")[0]
    hits = search(query_vector, top_k=top_k, doc_id=doc_id)

    for hit in hits:
        hit["above_threshold"] = hit["similarity"] >= MIN_SIMILARITY

    return {
        "question": question,
        "supported": any(hit["above_threshold"] for hit in hits),
        "best_similarity": max((hit["similarity"] for hit in hits), default=None),
        "threshold": MIN_SIMILARITY,
        "results": hits,
    }