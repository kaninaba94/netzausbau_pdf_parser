from pathlib import Path
import random

import pandas as pd


def collect_raw_measures_dfs_from_csvs(root_path: Path | str) -> list[pd.DataFrame]:
    root_path = Path(root_path)
    measures_dfs: list[pd.DataFrame] = list()
    for csv_path in Path(root_path).rglob('**/*csv'):
        measures_df: pd.DataFrame = pd.read_csv(csv_path)
        measures_df['source_file'] = str(csv_path).split('output/')[-1]
        measures_dfs.append(measures_df)
    return measures_dfs

def get_random_measure(measures_dfs: list[pd.DataFrame]) -> pd.Series:
    df = random.choice(measures_dfs)
    row_idx = random.choice(range(df.shape[0]))
    return df.iloc[row_idx]
