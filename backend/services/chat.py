from backend.services.llm import generate_answer
from backend.services.retriever import retrieve

NOT_FOUND_MESSAGE = "I couldn't find this in your documents."


def answer_question(question: str, doc_id: str | None = None) -> dict:
    retrieval = retrieve(question, doc_id=doc_id)

    # Pehli layer: retrieval ne kaha ke kuch qareeb hai hi nahi -> LLM ko bulao hi mat
    if not retrieval["supported"]:
        return _not_found(retrieval["best_similarity"])

    # Sirf threshold se upar wale chunks LLM ko denge
    passages = [hit for hit in retrieval["results"] if hit["above_threshold"]]
    result = generate_answer(question, passages)

    # Doosri layer: LLM ne khud kaha ke jawab context mein nahi
    if not result.answerable or not result.answer.strip():
        return _not_found(retrieval["best_similarity"])

    # Model ke diye hue source_ids ko check karo (1..len(passages) ke andar hon)
    used = []
    for source_id in result.source_ids:
        if 1 <= source_id <= len(passages) and passages[source_id - 1] not in used:
            used.append(passages[source_id - 1])

    # Guard: jawab hai lekin koi sahi source nahi -> verify nahi kar sakte, jawab nahi dikhate
    if not used:
        return _not_found(retrieval["best_similarity"])

    # Citations hamare database ke metadata se aati hain, model se nahi
    sources = []
    seen = set()
    for passage in used:
        key = (passage["filename"], passage["page"])
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            {
                "filename": passage["filename"],
                "page": passage["page"],
                "similarity": passage["similarity"],
                "snippet": passage["text"][:200],
            }
        )

    return {
        "answer": result.answer.strip(),
        "supported": True,
        "best_similarity": retrieval["best_similarity"],
        "sources": sources,
    }


def _not_found(best_similarity):
    return {
        "answer": NOT_FOUND_MESSAGE,
        "supported": False,
        "best_similarity": best_similarity,
        "sources": [],
    }