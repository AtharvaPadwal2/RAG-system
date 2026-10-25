from fastembed import TextEmbedding

model = TextEmbedding(
    model_name="BAAI/bge-small-en-v1.5",
    threads=2,
)

texts = [
    "Develop your knights and bishops during the opening.",
    "A knight fork attacks multiple opposing pieces.",
]

embeddings = list(model.embed(texts))

print("Texts embedded:", len(embeddings))
print("Dimensions per embedding:", len(embeddings[0]))
print("First 5 values:", embeddings[0][:5].tolist())