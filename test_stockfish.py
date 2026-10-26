from pathlib import Path

import chess
import chess.engine

engine_path = (
    Path(__file__).resolve().parent
    / "engines"
    / "stockfish"
    / "stockfish"
    / "stockfish-windows-x86-64-universal.exe"
)

if not engine_path.is_file():
    raise SystemExit(f"Stockfish executable not found: {engine_path}")

board = chess.Board()

with chess.engine.SimpleEngine.popen_uci(
    str(engine_path),
    timeout=15.0,
) as engine:
    engine.configure({
        "Threads": 1,
        "Hash": 64,
    })

    result = engine.analyse(
        board,
        chess.engine.Limit(time=1.0),
    )

    print("Engine:", engine.id.get("name", "Stockfish"))
    print("Suggested move:", board.san(result["pv"][0]))
    print("Evaluation from White's perspective:", result["score"].white())
    print("Search depth:", result.get("depth"))