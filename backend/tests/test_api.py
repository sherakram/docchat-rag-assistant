import pymupdf
import pytest
from fastapi.testclient import TestClient

from backend import main

DOC_ID = "a" * 32


def make_pdf(pages=1, text="The quick brown fox jumps over the lazy dog. " * 8):
    """Test ke liye asli (chhoti) PDF memory mein banao."""
    doc = pymupdf.open()
    for _ in range(pages):
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(72, 72, 520, 770), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def upload(client, data, name="doc.pdf"):
    return client.post("/api/upload", files={"file": (name, data, "application/pdf")})


@pytest.fixture
def client():
    # raise_server_exceptions=False: anjaan error par asli 500 jawab milta hai
    return TestClient(main.app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def fresh_limiters():
    main.chat_limiter.calls.clear()
    main.upload_limiter.calls.clear()


@pytest.fixture
def mocked_upload(monkeypatch, tmp_path):
    """Upload ke bahar ke hisse (Gemini, Chroma, disk) nakli, taake test tez aur free ho."""
    state = {"add_calls": 0, "dir": tmp_path}
    monkeypatch.setattr(main, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(main, "find_doc_by_hash", lambda content_hash: None)
    monkeypatch.setattr(main, "embed_texts", lambda texts: [[0.1, 0.2] for _ in texts])

    def fake_add(*args, **kwargs):
        state["add_calls"] += 1

    monkeypatch.setattr(main, "add_chunks", fake_add)
    return state


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_security_headers(client):
    headers = client.get("/api/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert "content-security-policy" in headers
    # Swagger UI (/docs) par CSP nahi, warna wo toot jata hai
    assert "content-security-policy" not in client.get("/docs").headers


def test_upload_rejects_wrong_extension(client):
    assert upload(client, b"hello", name="notes.txt").status_code == 400


def test_upload_rejects_fake_pdf(client):
    response = upload(client, b"just some text, not a pdf", name="fake.pdf")
    assert response.status_code == 400
    assert "not a valid PDF" in response.json()["detail"]


def test_upload_rejects_oversized_file(client, monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 100)
    assert upload(client, make_pdf()).status_code == 413


def test_upload_rejects_too_many_pages(client, mocked_upload, monkeypatch):
    monkeypatch.setattr(main, "MAX_PDF_PAGES", 1)
    response = upload(client, make_pdf(pages=2))
    assert response.status_code == 413
    assert "too many pages" in response.json()["detail"]
    assert mocked_upload["add_calls"] == 0


def test_upload_success_saves_file_and_indexes(client, mocked_upload):
    response = upload(client, make_pdf())
    assert response.status_code == 200
    body = response.json()
    assert body["chunk_count"] >= 1
    assert mocked_upload["add_calls"] == 1
    assert (mocked_upload["dir"] / f"{body['doc_id']}.pdf").exists()


def test_upload_duplicate_returns_409(client, mocked_upload, monkeypatch):
    monkeypatch.setattr(
        main, "find_doc_by_hash", lambda h: {"doc_id": DOC_ID, "filename": "old.pdf"}
    )
    response = upload(client, make_pdf())
    assert response.status_code == 409
    assert "already uploaded" in response.json()["detail"]
    assert mocked_upload["add_calls"] == 0


def test_delete_rejects_invalid_id(client):
    assert client.delete("/api/documents/abc").status_code == 400


def test_delete_unknown_document_404(client, monkeypatch):
    monkeypatch.setattr(main, "count_for_doc", lambda doc_id: 0)
    assert client.delete(f"/api/documents/{DOC_ID}").status_code == 404


def test_delete_removes_chunks_and_file(client, monkeypatch, tmp_path):
    pdf_path = tmp_path / f"{DOC_ID}.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    deleted = []
    monkeypatch.setattr(main, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(main, "count_for_doc", lambda doc_id: 3)
    monkeypatch.setattr(main, "delete_doc", lambda doc_id: deleted.append(doc_id))

    response = client.delete(f"/api/documents/{DOC_ID}")
    assert response.status_code == 200
    assert deleted == [DOC_ID]
    assert not pdf_path.exists()


def test_chat_unknown_document_404(client, monkeypatch):
    monkeypatch.setattr(main, "count_for_doc", lambda doc_id: 0)
    response = client.post("/api/chat", json={"question": "hi", "doc_id": DOC_ID})
    assert response.status_code == 404


def test_chat_rejects_empty_question(client):
    assert client.post("/api/chat", json={"question": "   "}).status_code == 422


def test_chat_rate_limit(client, monkeypatch):
    monkeypatch.setattr(main.chat_limiter, "max_calls", 2)
    monkeypatch.setattr(
        main,
        "answer_question",
        lambda question, doc_id=None: {
            "answer": "ok", "supported": True, "best_similarity": 0.9, "sources": [],
        },
    )
    statuses = [client.post("/api/chat", json={"question": "hi"}).status_code for _ in range(3)]
    assert statuses == [200, 200, 429]
    blocked = client.post("/api/chat", json={"question": "hi"})
    assert "retry-after" in blocked.headers


def test_unexpected_error_returns_generic_500(client, monkeypatch):
    def boom():
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(main, "list_documents", boom)
    response = client.get("/api/documents")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}
    assert "secret" not in response.text