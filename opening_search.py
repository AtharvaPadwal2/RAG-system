import io

import chess
import chess.pgn
import psycopg
from psycopg.rows import dict_row

from database import Settings


def search_openings(name: str, limit: int = 5):
    name = name.strip()

    if not name:
        return []

    limit = max(1, min(limit, 10))

    # Treat wildcard characters as literal search text.
    escaped = (
        name.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )

    settings = Settings()

    with psycopg.connect(
        settings.database_url.get_secret_value(),
        sslmode="require",
        connect_timeout=10,
        options="-c statement_timeout=10000",
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, eco_code, name, moves_pgn
                FROM public.openings
                WHERE name ILIKE %s ESCAPE E'\\\\'
                ORDER BY
                    CASE WHEN LOWER(name) = LOWER(%s)
                         THEN 0 ELSE 1 END,
                    LENGTH(moves_pgn),
                    name,
                    id
                LIMIT %s
                """,
                (f"%{escaped}%", name, limit),
            )
            openings = cursor.fetchall()

    results = []

    for opening in openings:
        game = chess.pgn.read_game(
            io.StringIO(opening["moves_pgn"])
        )

        if game is None or game.errors:
            continue

        results.append({
            "lesson_title": opening["name"],
            "fen": chess.STARTING_FEN,
            "moves": [
                move.uci() for move in game.mainline_moves()
            ],
            "arrows": [],
            "highlights": [],
            "caption": (
                f"{opening['eco_code']} — "
                f"{opening['moves_pgn']}. "
                "Opening line observed in our game dataset."
            ),
        })

    return results


if __name__ == "__main__":
    query = input("Opening name, e.g. Italian Game: ")

    for result in search_openings(query):
        print("\nOpening:", result["lesson_title"])
        print("Moves:", result["moves"])
        print("Caption:", result["caption"])