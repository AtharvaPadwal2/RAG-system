from pathlib import Path
import shutil

import kagglehub

download_path = Path(kagglehub.dataset_download("datasnaek/chess"))

data_folder = Path(__file__).resolve().parent / "data"
data_folder.mkdir(exist_ok=True)

source = download_path / "games.csv"
destination = data_folder / "games.csv"

shutil.copy2(source, destination)

print("Dataset saved to:", destination)