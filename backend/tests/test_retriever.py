import pytest

from backend.services import retriever


def fake_hit(similarity):
    return {
        "text": "some chunk text",
        "doc_id": "doc1",
        "filename": "file.pdf",
        "page": 1,
        "chunk_index": 0,
        "similarity": similarity,
    }


@pytest.fixture(autouse=True)
def no_real_api(monkeypatch):
    """Har test mein asli Gemini ki jagah nakli embedding aur fixed threshold."""
    monkeypatch.setattr(retriever, "embed_texts", lambda texts, task_type="": [[0.0]])
    monkeypatch.setattr(retriever, "MIN_SIMILARITY", 0.5)


def use_hits(monkeypatch, hits):
    monkeypatch.setattr(retriever, "search", lambda vec, top_k=4, doc_id=None: hits)


def test_supported_when_a_hit_is_above_threshold(monkeypatch):
    use_hits(monkeypatch, [fake_hit(0.8), fake_hit(0.3)])
    result = retriever.retrieve("question")
    assert result["supported"] is True
    assert result["best_similarity"] == 0.8
    assert [h["above_threshold"] for h in result["results"]] == [True, False]


def test_not_supported_when_all_hits_are_below_threshold(monkeypatch):
    use_hits(monkeypatch, [fake_hit(0.4), fake_hit(0.2)])
    result = retriever.retrieve("question")
    assert result["supported"] is False


def test_no_hits_means_not_supported(monkeypatch):
    use_hits(monkeypatch, [])
    result = retriever.retrieve("question")
    assert result["supported"] is False
    assert result["best_similarity"] is None


def test_threshold_boundary_is_inclusive(monkeypatch):
    use_hits(monkeypatch, [fake_hit(0.5)])
    assert retriever.retrieve("question")["supported"] is True


def test_doc_id_is_passed_to_search(monkeypatch):
    seen = {}

    def spy(vec, top_k=4, doc_id=None):
        seen["doc_id"] = doc_id
        return []

    monkeypatch.setattr(retriever, "search", spy)
    retriever.retrieve("question", doc_id="abc123")
    assert seen["doc_id"] == "abc123"


def test_question_is_embedded_as_a_query(monkeypatch):
    seen = {}

    def spy(texts, task_type=""):
        seen["task_type"] = task_type
        return [[0.0]]

    monkeypatch.setattr(retriever, "embed_texts", spy)
    use_hits(monkeypatch, [])
    retriever.retrieve("question")
    assert seen["task_type"] == "RETRIEVAL_QUERY"