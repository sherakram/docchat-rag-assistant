import sys

from backend.services.chat import answer_question

question = " ".join(sys.argv[1:]).strip()
if not question:
    print('Usage: python -m scripts.ask "your question"')
    sys.exit(1)

result = answer_question(question)
print("Supported:", result["supported"], "| best score:", result["best_similarity"])
print("Answer   :", result["answer"])
for s in result["sources"]:
    print(f"  source: {s['filename']} | page {s['page']} | {s['similarity']:.3f}")