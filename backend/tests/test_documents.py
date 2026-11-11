import pytest

from backend.services import vector_store

DOC_A = "a" * 32
DOC_B = "b" * 32


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Har test ko apna khali, alag database."""
    monkeypatch.setattr(vector_store, "CHROMA_DIR", tmp_path / "chroma")
    monkeypatch.setattr(vector_store, "_client", None)


def add_doc(doc_id, filename, content_hash, vector, pages=2):
    chunks = [{"chunk_index": i, "page": i + 1, "text": f"text {i}"} for i in range(pages)]
    vector_store.add_chunks(
        doc_id,
        filename,
        chunks,
        [vector for _ in chunks],
        content_hash=content_hash,
        page_count=10,
        uploaded_at="2026-01-01T00:00:00+00:00",
    )


def test_list_documents_groups_chunks_by_doc():
    add_doc(DOC_A, "a.pdf", "hash-a", [1.0, 0.0, 0.0], pages=3)
    add_doc(DOC_B, "b.pdf", "hash-b", [0.0, 1.0, 0.0], pages=2)
    docs = {d["doc_id"]: d for d in vector_store.list_documents()}
    assert set(docs) == {DOC_A, DOC_B}
    assert docs[DOC_A]["chunk_count"] == 3
    assert docs[DOC_B]["chunk_count"] == 2
    assert docs[DOC_A]["filename"] == "a.pdf"
    assert docs[DOC_A]["page_count"] == 10


def test_find_doc_by_hash():
    add_doc(DOC_A, "a.pdf", "hash-a", [1.0, 0.0, 0.0])
    assert vector_store.find_doc_by_hash("hash-a")["doc_id"] == DOC_A
    assert vector_store.find_doc_by_hash("hash-a")["filename"] == "a.pdf"
    assert vector_store.find_doc_by_hash("other-hash") is None


def test_delete_removes_only_that_document():
    add_doc(DOC_A, "a.pdf", "hash-a", [1.0, 0.0, 0.0])
    add_doc(DOC_B, "b.pdf", "hash-b", [0.0, 1.0, 0.0])
    vector_store.delete_doc(DOC_A)
    assert vector_store.count_for_doc(DOC_A) == 0
    assert vector_store.count_for_doc(DOC_B) == 2


def test_search_can_be_limited_to_one_document():
    add_doc(DOC_A, "a.pdf", "hash-a", [1.0, 0.0, 0.0])
    add_doc(DOC_B, "b.pdf", "hash-b", [0.0, 1.0, 0.0])
    everywhere = vector_store.search([1.0, 0.0, 0.0], top_k=4)
    assert everywhere[0]["doc_id"] == DOC_A
    only_b = vector_store.search([1.0, 0.0, 0.0], top_k=4, doc_id=DOC_B)
    assert only_b and all(hit["doc_id"] == DOC_B for hit in only_b)


def test_legacy_documents_without_new_metadata_are_listed():
    # Milestone 4-7 ki purani upload: hash, date aur page_count nahi
    vector_store._collection().add(
        ids=["old_0"],
        embeddings=[[1.0, 0.0, 0.0]],
        documents=["old text"],
        metadatas=[{"doc_id": "c" * 32, "filename": "old.pdf", "page": 3, "chunk_index": 0}],
    )
    docs = vector_store.list_documents()
    assert len(docs) == 1
    assert docs[0]["filename"] == "old.pdf"
    assert docs[0]["page_count"] == 3
    assert docs[0]["uploaded_at"] == ""