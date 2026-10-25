import psycopg
from fastembed import TextEmbedding

from database import Settings

MODEL_NAME = "BAAI/bge-small-en-v1.5"

question = input("Ask a chess question: ").strip()

if not question:
    raise SystemExit("Please enter a question.")

model = TextEmbedding(model_name=MODEL_NAME, threads=2)

# BGE uses this instruction for retrieval queries.
query_text = (
    "Represent this sentence for searching relevant passages: "
    + question
)

vector = next(iter(model.embed([query_text])))
vector_literal = "[" + ",".join(
    str(float(value)) for value in vector
) + "]"

settings = Settings()

with psycopg.connect(
    settings.database_url.get_secret_value(),
    sslmode="require",
    connect_timeout=10,
) as connection:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                l.title,
                c.content,
                1 - (
                    c.embedding <=> %s::extensions.vector
                ) AS similarity
            FROM public.lesson_chunks AS c
            JOIN public.lessons AS l ON l.id = c.lesson_id
            WHERE c.embedding_model = %s
            ORDER BY c.embedding <=> %s::extensions.vector
            LIMIT 3
            """,
            (vector_literal, MODEL_NAME, vector_literal),
        )
        results = cursor.fetchall()

for title, content, similarity in results:
    # Starting value for testing, not a proven relevance boundary.
 MIN_SIMILARITY = 0.60

matches = [
    result for result in results
    if result[2] >= MIN_SIMILARITY
]

if not matches:
    print("\nNo sufficiently relevant lesson found in our knowledge base.")
else:
    for title, content, similarity in matches:
        print(f"\n{title} | Similarity: {similarity:.3f}")
        print(content)