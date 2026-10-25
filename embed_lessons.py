from fastembed import TextEmbedding
import psycopg

from database import Settings

MODEL_NAME = "BAAI/bge-small-en-v1.5"

settings = Settings()
database_url = settings.database_url.get_secret_value()

# Fetch the lessons, then close the connection during model processing.
with psycopg.connect(
    database_url,
    sslmode="require",
    connect_timeout=10,
) as connection:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, title, content FROM public.lessons ORDER BY id"
        )
        lessons = cursor.fetchall()

if not lessons:
    print("No lessons found.")
    raise SystemExit(0)

model = TextEmbedding(model_name=MODEL_NAME, threads=2)

# These starter lessons are short enough for one chunk each.
texts = [f"{title}\n\n{content}" for _, title, content in lessons]
embeddings = model.embed(texts)

with psycopg.connect(
    database_url,
    sslmode="require",
    connect_timeout=10,
) as connection:
    with connection.cursor() as cursor:
        for (lesson_id, _, _), text, vector in zip(
            lessons, texts, embeddings, strict=True
        ):
            vector_literal = "[" + ",".join(
                str(float(value)) for value in vector
            ) + "]"

            cursor.execute(
                """
                INSERT INTO public.lesson_chunks (
                    lesson_id, chunk_index, content,
                    embedding, embedding_model
                )
                VALUES (%s, 0, %s, %s::extensions.vector, %s)
                ON CONFLICT (lesson_id, chunk_index)
                DO UPDATE SET
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    embedding_model = EXCLUDED.embedding_model
                """,
                (lesson_id, text, vector_literal, MODEL_NAME),
            )

print("Lesson chunks embedded and saved:", len(lessons))