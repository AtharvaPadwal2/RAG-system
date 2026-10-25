from pathlib import Path

import pandas as pd

csv_path = Path(__file__).resolve().parent / "data" / "games.csv"
df = pd.read_csv(csv_path)

print("Rows and columns:", df.shape)

print("\nColumn names:")
print(df.columns.tolist())

print("\nMissing values:")
print(df.isna().sum())

print("\nDuplicate rows:", df.duplicated().sum())

print("\nFirst 3 rows:")
print(df.head(3).to_string(index=False))