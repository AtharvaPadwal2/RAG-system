from pathlib import Path
from threading import Lock

import chess
import chess.engine

ENGINE_PATH = (
    Path(__file__).resolve().parent
    / "engines"
    / "stockfish"
    / "stockfish"
    / "stockfish-windows-x86-64-universal.exe"
)

# Allow one analysis at a time within this Python process.
ENGINE_LOCK = Lock()


class EngineBusyError(Exception):
    pass


def analyse_position(fen: str):
    board = chess.Board(fen)

    if not board.is_valid():
        raise ValueError("Invalid chess position.")

    # No suggested move when the position has already ended.
    if board.is_game_over():
        return {
            "fen": board.fen(),
            "status": "game_over",
            "result": board.result(),
            "best_move_uci": None,
            "best_move_san": None,
            "score_cp": None,
            "mate_in": None,
            "depth": None,
            "continuation": [],
        }

    if not ENGINE_PATH.is_file():
        raise FileNotFoundError("Stockfish executable not found.")

    if not ENGINE_LOCK.acquire(blocking=False):
        raise EngineBusyError("Another analysis is running.")

    try:
        with chess.engine.SimpleEngine.popen_uci(
            str(ENGINE_PATH),
            timeout=15.0,
        ) as engine:
            engine.configure({
                "Threads": 1,
                "Hash": 64,
            })

            info = engine.analyse(
                board,
                chess.engine.Limit(time=1.0),
            )

        principal_variation = info.get("pv", [])

        if not principal_variation:
            raise RuntimeError("Stockfish returned no continuation.")

        score = info["score"].white()
        best_move = principal_variation[0]

        return {
            "fen": board.fen(),
            "status": "analysed",
            "result": None,
            "best_move_uci": best_move.uci(),
            "best_move_san": board.san(best_move),
            "score_cp": score.score(),
            "mate_in": score.mate(),
            "depth": info.get("depth"),
            "continuation": [
                move.uci()
                for move in principal_variation[:10]
            ],
        }

    finally:
        ENGINE_LOCK.release()

DIFFICULTY_SETTINGS = {
    "easy": {"skill": 0, "time": 0.1},
    "medium": {"skill": 5, "time": 0.3},
    "hard": {"skill": 12, "time": 0.7},
    "extreme": {"skill": 20, "time": 1.0},
}


def play_stockfish(fen: str, difficulty: str):
    if difficulty not in DIFFICULTY_SETTINGS:
        raise ValueError("Invalid difficulty.")

    board = chess.Board(fen)

    if not board.is_valid():
        raise ValueError("Invalid chess position.")

    def build_response(move_uci=None, move_san=None):
        # FEN cannot preserve repetition history.
        outcome = board.outcome(claim_draw=False)

        return {
            "status": "game_over" if outcome else "played",
            "fen": board.fen(),
            "move_uci": move_uci,
            "move_san": move_san,
            "game_over": outcome is not None,
            "result": outcome.result() if outcome else None,
            "termination": (
                outcome.termination.name.lower()
                if outcome
                else None
            ),
        }

    if board.outcome(claim_draw=False):
        return build_response()

    if not ENGINE_PATH.is_file():
        raise FileNotFoundError("Stockfish executable not found.")

    if not ENGINE_LOCK.acquire(blocking=False):
        raise EngineBusyError("Another analysis is running.")

    try:
        settings = DIFFICULTY_SETTINGS[difficulty]

        with chess.engine.SimpleEngine.popen_uci(
            str(ENGINE_PATH),
            timeout=15.0,
        ) as engine:
            options = {
                "Threads": 1,
                "Hash": 64,
                "Skill Level": settings["skill"],
            }

            if "UCI_LimitStrength" in engine.options:
                options["UCI_LimitStrength"] = False

            engine.configure(options)

            result = engine.play(
                board,
                chess.engine.Limit(time=settings["time"]),
            )

            move = result.move

            if move is None or move not in board.legal_moves:
                raise RuntimeError(
                    "Stockfish returned no legal move."
                )

            move_uci = move.uci()
            move_san = board.san(move)

            board.push(move)

            return build_response(move_uci, move_san)

    finally:
        ENGINE_LOCK.release()