import chess
import psycopg
from psycopg.rows import dict_row

from database import Settings


def search_games(opening_name: str, limit: int = 3):
    opening_name = opening_name.strip()

    if not opening_name:
        return []

    limit = max(1, min(limit, 5))

    escaped = (
        opening_name.replace("\\", "\\\\")
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
                SELECT
                    id, opening_name, opening_eco,
                    white_rating, black_rating,
                    winner, victory_status, moves
                FROM public.games
                WHERE opening_name ILIKE %s ESCAPE E'\\\\'
                ORDER BY
                    CASE WHEN LOWER(opening_name) = LOWER(%s)
                         THEN 0 ELSE 1 END,
                    id
                LIMIT %s
                """,
                (f"%{escaped}%", opening_name, limit),
            )
            games = cursor.fetchall()

    results = []

    for game in games:
        board = chess.Board()
        moves = []

        for token in game["moves"].split():
            move = board.parse_san(token)
            moves.append(move.uci())
            board.push(move)

        results.append({
            "lesson_title": (
                f"{game['opening_name']} — Game {game['id']}"
            ),
            "fen": chess.STARTING_FEN,
            "moves": moves,
            "arrows": [],
            "highlights": [],
            "caption": (
                f"White rating: {game['white_rating']} | "
                f"Black rating: {game['black_rating']} | "
                f"Recorded result: {game['winner']} | "
                f"Ending: {game['victory_status']}. "
                "Example game from our dataset, not an "
                "engine-recommended continuation."
            ),
        })

    return results


if __name__ == "__main__":
    name = input("Opening name: ")

    results = search_games(name)

    if not results:
        print("No matching games found.")

    for result in results:
        print("\nGame:", result["lesson_title"])
        print("Half-moves:", len(result["moves"]))
        print("Caption:", result["caption"])