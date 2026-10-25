import json
from pathlib import Path

import psycopg

from database import Settings

path = Path(__file__).resolve().parent / "data" / "lessons.json"
lessons = json.loads(path.read_text(encoding="utf-8"))

query = """
    INSERT INTO public.lessons (
        title, topic, difficulty, content, is_published
    )
    SELECT %s, %s, %s, %s, false
    WHERE NOT EXISTS (
        SELECT 1
        FROM public.lessons
        WHERE title = %s AND content = %s
    )
"""

settings = Settings()
inserted = 0

with psycopg.connect(
    settings.database_url.get_secret_value(),
    sslmode="require",
    connect_timeout=10,
) as connection:
    with connection.cursor() as cursor:
        for lesson in lessons:
            cursor.execute(
                query,
                (
                    lesson["title"],
                    lesson["topic"],
                    lesson["difficulty"],
                    lesson["content"],
                    lesson["title"],
                    lesson["content"],
                ),
            )
            inserted += cursor.rowcount

print("New draft lessons imported:", inserted)