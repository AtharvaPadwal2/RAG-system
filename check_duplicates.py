from pathlib import Path

import pandas as pd

path = Path(__file__).resolve().parent / "data" / "games_clean.csv"
df = pd.read_csv(path)

repeated = df[df.duplicated(subset="id", keep=False)]

print("Game IDs appearing multiple times:", repeated["id"].nunique())

differences = repeated.groupby("id").nunique(dropna=False)
conflicts = differences.gt(1).sum().sort_values(ascending=False)

print("\nNumber of repeated game IDs differing in each column:")
print(conflicts[conflicts > 0].to_string())

print("\nColumns differing for the first 5 repeated game IDs:")
for game_id, group in list(repeated.groupby("id"))[:5]:
    changed = group.nunique(dropna=False)
    print(game_id, ":", changed[changed > 1].index.tolist())