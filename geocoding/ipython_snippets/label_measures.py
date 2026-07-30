import random
from pathlib import Path
import json

import numpy as np
import pandas as pd

DATASET_PATH = './artefacts/01_sampled_measures_labelled.json'

def get_random_measure() -> pd.Series:
    df = random.choice(measures_dfs)
    row_idx = random.choice(range(df.shape[0]))
    return df.iloc[row_idx]

def _input(prompt: str, options: dict, collection: bool = False) -> bool:
    options_hint = ", ".join([f"{k} for {v}" for k, v in options.items()])
    assert isinstance(collection, bool)
    user_input = input(f"{prompt}   {options_hint}")
    while not user_input in options.keys():
        user_input = input(prompt)
    return options[user_input]

def _get_row_hash(row: pd.Series) -> int:
    return int(
        pd.util.hash_pandas_object(row).sum()
    )

dataset_path = Path(DATASET_PATH)
if not dataset_path.exists():
    raise FileNotFoundError(f'{dataset_path} does not exist.\n`touch "[]" > {dataset_path} and try again`')
with open(dataset_path, 'r') as f:
    sampled_measures = json.load(f)
    
measures_dfs: list[pd.DataFrame] = list()
for csv_path in Path('../pdfplumber_table_extraction/output/').rglob('**/*csv'):
    measures_df: pd.DataFrame = pd.read_csv(csv_path)
    measures_df['source_file'] = str(csv_path).split('output/')[-1]
    measures_dfs.append(measures_df)
    
     
try:
    while True:
        current = get_random_measure()
        row_hash = _get_row_hash(current)
        if row_hash in set([r['measure_row_hash'] for r in sampled_measures]):
            print('measure already labelled. continue to next one')
            continue
        print('\n\n')
        print(current)
        current_dict = {
            k: int(v) if isinstance(v, np.integer) else v for k, v in current.items()
        }
        current_dict['measure_row_hash'] = row_hash
        current_dict['label:asset_type'] = _input('Asset type', {'uw': 'transformer_station', 'pl': 'power_line', 'o': None})
        current_dict['label:existing'] = _input('Does the asset exist already?', {'y': True, 'n': False, 'o': None})
        if current_dict['label:asset_type'] == 'transformer_station' and current_dict['label:existing'] is True:
            if _input('Easy to geocode? (y/n)', {'y': True, 'n': False}):
                current_dict['label:easy_to_geocode'] = True
            if current_dict['label:easy_to_geocode'] is True:
                current_dict['label:location_clues'] = []
                while True:
                    try:
                        current_dict['label:location_clues'].append(input('Type location clue (ctrl+c to stop):   '))
                    except KeyboardInterrupt:
                        break
        
        sampled_measures.append(current_dict)
except KeyboardInterrupt:
    pass
    
with open(dataset_path, 'w') as f:
    json.dump(sampled_measures, f)
