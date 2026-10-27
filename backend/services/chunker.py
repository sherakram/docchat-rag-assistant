def chunk_pages(
    pages: list[dict],
    chunk_size: int = 200,
    overlap: int = 40,
    min_words: int = 5,
) -> list[dict]:
    """Page-wise text ko overlapping chunks mein todo.

    Input:  [{"page": 1, "text": "..."}, ...]
    Output: [{"chunk_index": 0, "page": 1, "text": "..."}, ...]

    Har chunk sirf ek page ka hota hai, taake citation seedhi rahe.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and smaller than chunk_size")

    step = chunk_size - overlap
    chunks: list[dict] = []

    for page in pages:
        words = page["text"].split()
        if not words:
            continue

        start = 0
        while start < len(words):
            piece = words[start : start + chunk_size]

            if len(piece) >= min_words:
                chunks.append(
                    {
                        "chunk_index": len(chunks),
                        "page": page["page"],
                        "text": " ".join(piece),
                    }
                )

            if start + chunk_size >= len(words):
                break
            start += step

    return chunks