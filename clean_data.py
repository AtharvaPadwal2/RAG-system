from pathlib import Path

import pandas as pd

data_folder = Path(__file__).resolve().parent / "data"
df = pd.read_csv(data_folder / "games.csv")

original_count = len(df)
df = df.drop_duplicates()
exact_removed = original_count - len(df)

# Stop if records with the same ID disagree beyond timestamps.
chess_columns = [
    column for column in df.columns
    if column not in ["id", "created_at", "last_move_at"]
]

differences = df.groupby("id")[chess_columns].nunique(dropna=False)

if differences.gt(1).any().any():
    raise ValueError("Conflicting game data found. Review before removing rows.")

before = len(df)
df = df.drop_duplicates(subset="id", keep="first")

output_path = data_folder / "games_clean.csv"
df.to_csv(output_path, index=False)

print("Exact duplicates removed:", exact_removed)
print("Repeated ID rows removed:", before - len(df))
print("Unique games:", len(df))
print("Saved to:", output_path)