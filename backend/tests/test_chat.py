import pytest

from backend.services import chat
from backend.services.llm import LLMAnswer


def hit(page, similarity, above, text="some text", filename="a.pdf"):
    return {
        "text": text,
        "doc_id": "d1",
        "filename": filename,
        "page": page,
        "chunk_index": page,
        "similarity": similarity,
        "above_threshold": above,
    }


def retrieval(supported, hits):
    return {
        "question": "q",
        "supported": supported,
        "best_similarity": max((h["similarity"] for h in hits), default=None),
        "threshold": 0.5,
        "results": hits,
    }


@pytest.fixture
def llm_calls(monkeypatch):
    """LLM ke calls ginta hai, taake pata chale ke bulaya gaya ya nahi."""
    calls = []
    monkeypatch.setattr(chat, "generate_answer", lambda q, passages: calls.append(passages) or LLMAnswer(
        answerable=True, answer="The answer.", source_ids=[1]
    ))
    return calls


def test_unsupported_retrieval_skips_the_llm(monkeypatch, llm_calls):
    monkeypatch.setattr(chat, "retrieve", lambda q, doc_id=None: retrieval(False, [hit(1, 0.3, False)]))
    result = chat.answer_question("q")
    assert result["supported"] is False
    assert result["answer"] == chat.NOT_FOUND_MESSAGE
    assert result["sources"] == []
    assert llm_calls == []  # LLM bulaya hi nahi gaya


def test_answer_gets_sources_from_metadata(monkeypatch, llm_calls):
    monkeypatch.setattr(chat, "retrieve", lambda q, doc_id=None: retrieval(True, [hit(7, 0.8, True)]))
    result = chat.answer_question("q")
    assert result["supported"] is True
    assert result["answer"] == "The answer."
    assert result["sources"][0]["page"] == 7
    assert result["sources"][0]["filename"] == "a.pdf"


def test_only_above_threshold_passages_reach_the_llm(monkeypatch, llm_calls):
    hits = [hit(1, 0.8, True), hit(2, 0.3, False)]
    monkeypatch.setattr(chat, "retrieve", lambda q, doc_id=None: retrieval(True, hits))
    chat.answer_question("q")
    assert len(llm_calls) == 1
    assert [p["page"] for p in llm_calls[0]] == [1]


def test_model_saying_not_answerable_gives_not_found(monkeypatch):
    monkeypatch.setattr(chat, "retrieve", lambda q, doc_id=None: retrieval(True, [hit(1, 0.8, True)]))
    monkeypatch.setattr(chat, "generate_answer", lambda q, p: LLMAnswer(
        answerable=False, answer="", source_ids=[]
    ))
    result = chat.answer_question("q")
    assert result["supported"] is False
    assert result["sources"] == []


def test_invalid_source_ids_give_not_found(monkeypatch):
    monkeypatch.setattr(chat, "retrieve", lambda q, doc_id=None: retrieval(True, [hit(1, 0.8, True)]))
    monkeypatch.setattr(chat, "generate_answer", lambda q, p: LLMAnswer(
        answerable=True, answer="Made-up answer", source_ids=[99]
    ))
    result = chat.answer_question("q")
    assert result["supported"] is False
    assert result["answer"] == chat.NOT_FOUND_MESSAGE


def test_sources_are_deduplicated_by_page(monkeypatch):
    hits = [hit(3, 0.8, True, text="one"), hit(3, 0.7, True, text="two")]
    monkeypatch.setattr(chat, "retrieve", lambda q, doc_id=None: retrieval(True, hits))
    monkeypatch.setattr(chat, "generate_answer", lambda q, p: LLMAnswer(
        answerable=True, answer="Answer", source_ids=[1, 2]
    ))
    result = chat.answer_question("q")
    assert len(result["sources"]) == 1
    assert result["sources"][0]["page"] == 3