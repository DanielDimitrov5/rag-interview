import ollama

texts = [
    "When should I use cursor pagination?",
    "Cursor pagination works well for large changing datasets.",
]

response = ollama.embed(
    model="nomic-embed-text",
    input=texts,
)

embeddings = response["embeddings"]

print(f"Vectors returned: {len(embeddings)}")
print(f"Dimensions per vector: {len(embeddings[0])}")
print(f"First five values: {embeddings[0][:5]}")