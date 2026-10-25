from pathlib import Path

import chess
import pandas as pd

data_folder = Path(__file__).resolve().parent / "data"
df = pd.read_csv(data_folder / "games_clean.csv")

valid_rows = []
invalid_rows = []

for _, row in df.iterrows():
    board = chess.Board()

    try:
        moves = str(row["moves"]).split()

        if not moves:
            raise ValueError("Empty move sequence")

        for move in moves:
            board.push_san(move)

        valid_rows.append(row.to_dict())

    except ValueError as error:
        record = row.to_dict()
        record["validation_error"] = str(error)
        invalid_rows.append(record)

pd.DataFrame(valid_rows, columns=df.columns).to_csv(
    data_folder / "games_valid.csv",
    index=False,
)

pd.DataFrame(
    invalid_rows,
    columns=[*df.columns, "validation_error"],
).to_csv(
    data_folder / "games_invalid.csv",
    index=False,
)

print("Games checked:", len(df))
print("Valid move sequences:", len(valid_rows))
print("Invalid move sequences:", len(invalid_rows))