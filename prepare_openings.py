from pathlib import Path

import chess
import pandas as pd

data_folder = Path(__file__).resolve().parent / "data"
games = pd.read_csv(data_folder / "games_valid.csv")

records = []

for row in games.itertuples(index=False):
    tokens = row.moves.split()
    ply = int(row.opening_ply)

    if not 0 < ply <= len(tokens):
        raise ValueError(f"Invalid opening length for game {row.id}")

    board = chess.Board()
    numbered_moves = []

    for token in tokens[:ply]:
        move = board.parse_san(token)
        san = board.san(move)

        if board.turn == chess.WHITE:
            numbered_moves.append(f"{board.fullmove_number}. {san}")
        else:
            numbered_moves.append(san)

        board.push(move)

    records.append({
        "eco_code": row.opening_eco,
        "name": row.opening_name,
        "moves_pgn": " ".join(numbered_moves),
    })

openings = pd.DataFrame(records).drop_duplicates()
output_path = data_folder / "openings.csv"
openings.to_csv(output_path, index=False)

print("Unique opening records:", len(openings))
print("Saved to:", output_path)
print(openings.head(5).to_string(index=False))