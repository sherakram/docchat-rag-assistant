import pytest

from backend.services.chunker import chunk_pages


def make_text(n_words: int) -> str:
    """'w0 w1 w2 ...' jaisa nakli text, taake har word pehchana ja sake."""
    return " ".join(f"w{i}" for i in range(n_words))


def test_short_page_gives_one_chunk():
    pages = [{"page": 1, "text": make_text(50)}]
    chunks = chunk_pages(pages, chunk_size=100, overlap=20)
    assert len(chunks) == 1
    assert chunks[0]["page"] == 1
    assert chunks[0]["chunk_index"] == 0


def test_long_page_is_split_and_respects_size():
    pages = [{"page": 1, "text": make_text(250)}]
    chunks = chunk_pages(pages, chunk_size=100, overlap=20)
    assert len(chunks) == 3
    assert all(len(c["text"].split()) <= 100 for c in chunks)


def test_chunks_overlap_correctly():
    pages = [{"page": 1, "text": make_text(250)}]
    chunks = chunk_pages(pages, chunk_size=100, overlap=20)
    first_words = chunks[0]["text"].split()
    second_words = chunks[1]["text"].split()
    assert first_words[-20:] == second_words[:20]


def test_no_words_are_lost():
    pages = [{"page": 1, "text": make_text(250)}]
    chunks = chunk_pages(pages, chunk_size=100, overlap=20)
    assert "w249" in chunks[-1]["text"].split()
    assert chunks[0]["text"].split()[0] == "w0"


def test_chunks_never_cross_pages():
    pages = [
        {"page": 1, "text": make_text(30)},
        {"page": 2, "text": "alpha " * 30},
    ]
    chunks = chunk_pages(pages, chunk_size=100, overlap=20)
    assert [c["page"] for c in chunks] == [1, 2]
    assert "alpha" not in chunks[0]["text"]
    assert "w0" not in chunks[1]["text"]


def test_empty_and_tiny_pages_are_skipped():
    pages = [
        {"page": 1, "text": ""},
        {"page": 2, "text": "3"},  # sirf page number
        {"page": 3, "text": make_text(20)},
    ]
    chunks = chunk_pages(pages, chunk_size=100, overlap=20)
    assert [c["page"] for c in chunks] == [3]


def test_chunk_index_is_sequential_across_pages():
    pages = [
        {"page": 1, "text": make_text(250)},
        {"page": 2, "text": make_text(250)},
    ]
    chunks = chunk_pages(pages, chunk_size=100, overlap=20)
    assert [c["chunk_index"] for c in chunks] == list(range(len(chunks)))


def test_extra_whitespace_is_cleaned():
    pages = [{"page": 1, "text": "hello   world\n\n\nthis   is\ta test of spaces"}]
    chunks = chunk_pages(pages, chunk_size=100, overlap=20)
    assert chunks[0]["text"] == "hello world this is a test of spaces"


def test_invalid_settings_raise_error():
    pages = [{"page": 1, "text": make_text(50)}]
    with pytest.raises(ValueError):
        chunk_pages(pages, chunk_size=100, overlap=100)
    with pytest.raises(ValueError):
        chunk_pages(pages, chunk_size=0, overlap=0)