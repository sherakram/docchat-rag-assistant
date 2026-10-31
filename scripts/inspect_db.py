from backend.services.vector_store import peek, total_count

print("Total chunks stored:", total_count())
records = peek(5)
for meta, text in zip(records["metadatas"], records["documents"]):
    print(f"- {meta['filename']} | page {meta['page']} | chunk {meta['chunk_index']}")
    print("   ", text[:80], "...")