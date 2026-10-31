import sys

from backend.services.retriever import retrieve

question = " ".join(sys.argv[1:]).strip()
if not question:
    print('Usage: python -m scripts.try_search "your question here"')
    sys.exit(1)

result = retrieve(question)
print("Question  :", question)
print("Supported :", result["supported"])
print("Best score:", result["best_similarity"], "| threshold:", result["threshold"])
for hit in result["results"]:
    flag = "YES" if hit["above_threshold"] else "no "
    print(f"  [{flag}] {hit['similarity']:.3f} | {hit['filename']} | page {hit['page']}")
    print("        ", hit["text"][:90].replace("\n", " "), "...")