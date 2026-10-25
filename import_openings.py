from pathlib import Path

import pandas as pd
import psycopg

from database import Settings

csv_path = Path(__file__).resolve().parent / "data" / "openings.csv"
df = pd.read_csv(csv_path)

records = [
    (
        row.eco_code,
        row.name,
        row.moves_pgn,
        "https://www.kaggle.com/datasets/datasnaek/chess",
    )
    for row in df.itertuples(index=False)
]

query = """
    INSERT INTO public.openings (
        eco_code, name, moves_pgn, source_url
    )
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (eco_code, name, moves_pgn) DO NOTHING
"""

settings = Settings()

with psycopg.connect(
    settings.database_url.get_secret_value(),
    sslmode="require",
    connect_timeout=10,
) as connection:
    with connection.cursor() as cursor:
        cursor.executemany(query, records)
        inserted = cursor.rowcount

        cursor.execute("SELECT COUNT(*) FROM public.openings")
        total = cursor.fetchone()[0]

print("New opening records imported:", inserted)
print("Total opening records:", total)