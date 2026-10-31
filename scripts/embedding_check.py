import math

from backend.services.embeddings import embed_texts


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


sentences = [
    "How do I reset my password?",
    "Steps to recover a forgotten login password",
    "The mitochondria is the powerhouse of the cell",
]
vectors = embed_texts(sentences)

print("dimensions:", len(vectors[0]))
print("password vs recover     :", round(cosine(vectors[0], vectors[1]), 3))
print("password vs mitochondria:", round(cosine(vectors[0], vectors[2]), 3))