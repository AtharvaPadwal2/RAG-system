from pathlib import Path

import pandas as pd
import psycopg

from database import Settings

csv_path = Path(__file__).resolve().parent / "data" / "games_valid.csv"
df = pd.read_csv(csv_path)

columns = [
    "id",
    "rated",
    "white_rating",
    "black_rating",
    "winner",
    "victory_status",
    "increment_code",
    "moves",
    "opening_eco",
    "opening_name",
    "opening_ply",
]

records = list(df[columns].itertuples(index=False, name=None))

query = """
    INSERT INTO public.games (
        id, rated, white_rating, black_rating,
        winner, victory_status, time_control, moves,
        opening_eco, opening_name, opening_ply
    )
    VALUES (
        %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s
    )
    ON CONFLICT (id) DO NOTHING
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

        cursor.execute("SELECT COUNT(*) FROM public.games")
        total = cursor.fetchone()[0]

print("New games imported:", inserted)
print("Total games in database:", total)