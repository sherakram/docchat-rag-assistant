import json
import sys
import time
from pathlib import Path

from backend.config import MIN_SIMILARITY, TOP_K
from backend.services.embeddings import EmbeddingError
from backend.services.retriever import retrieve

QUESTIONS_FILE = Path("eval/questions.json")
SWEEP = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75]


def load_questions():
    if not QUESTIONS_FILE.exists():
        print("Missing eval/questions.json. Copy eval/questions.example.json and fill it in.")
        sys.exit(1)
    data = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    return data.get("in_scope", []), data.get("out_of_scope", [])


def first_correct_rank(results, filename, pages):
    """Sahi page top-k mein kis number par aaya (1 = sab se upar). Nahi aaya to None."""
    for rank, hit in enumerate(results, start=1):
        if hit["filename"] == filename and hit["page"] in pages:
            return rank
    return None


def pct(part, whole):
    return f"{100 * part / whole:.0f}%" if whole else "n/a"


def main():
    in_scope, out_scope = load_questions()
    ranks, in_best, out_best = [], [], []

    print(f"Threshold {MIN_SIMILARITY} | top_k {TOP_K}\n")
    print("IN-SCOPE questions")
    try:
        for item in in_scope:
            result = retrieve(item["question"])
            rank = first_correct_rank(result["results"], item["filename"], item["pages"])
            best = result["best_similarity"] or 0.0
            ranks.append(rank)
            in_best.append(best)
            tag = f"rank {rank}" if rank else "MISS  "
            verdict = "accepted" if result["supported"] else "REFUSED"
            print(f"  [{tag}] best {best:.3f} {verdict} | {item['question'][:60]}")
            time.sleep(0.4)

        print("\nOUT-OF-SCOPE questions")
        for question in out_scope:
            result = retrieve(question)
            best = result["best_similarity"] or 0.0
            out_best.append(best)
            verdict = "refused" if not result["supported"] else "ACCEPTED (leak)"
            print(f"  best {best:.3f} {verdict} | {question[:60]}")
            time.sleep(0.4)
    except EmbeddingError as exc:
        print("Stopped:", exc)
        sys.exit(1)

    found = [r for r in ranks if r]
    print("\nSUMMARY")
    print(f"  Recall@{TOP_K} (right page in top results): {pct(len(found), len(ranks))}")
    if ranks:
        mrr = sum(1 / r for r in found) / len(ranks)
        print(f"  Mean reciprocal rank: {mrr:.2f} (1.00 = right page always first)")
    print(f"  In-scope accepted by threshold: {pct(sum(b >= MIN_SIMILARITY for b in in_best), len(in_best))}")
    print(f"  Out-of-scope refused by threshold: {pct(sum(b < MIN_SIMILARITY for b in out_best), len(out_best))}")

    if in_best and out_best:
        lowest_in, highest_out = min(in_best), max(out_best)
        print(f"  Lowest in-scope score: {lowest_in:.3f} | highest out-of-scope score: {highest_out:.3f}")
        if lowest_in > highest_out:
            print(f"  Clean gap. A threshold near {(lowest_in + highest_out) / 2:.2f} separates them.")
        else:
            print("  Scores overlap: no single threshold separates them. The LLM layer must catch the rest.")

        print("\nTHRESHOLD SWEEP")
        print("  threshold | in-scope accepted | out-of-scope refused")
        for t in SWEEP:
            print(
                f"  {t:.2f}      | {pct(sum(b >= t for b in in_best), len(in_best)):>17} "
                f"| {pct(sum(b < t for b in out_best), len(out_best)):>20}"
            )


main()