import random
import os
import json
from tqdm import tqdm
from pathlib import Path

from ipython_snippets.label_measures import collect_raw_measures_dfs_from_csvs, get_random_measure
from cursor_sdk import Agent, LocalAgentOptions
from json_extractor import JsonExtractor

OUT_DIR = Path('./artefacts')

with open('artefacts/01_sampled_measures_labelled.json', 'r') as f:
    sampled_measures = json.load(f)
    
with_clues = [m for m in sampled_measures if 'label:location_clues' in m.keys()]
measures_dfs = collect_raw_measures_dfs_from_csvs('../table_extraction/')
random_measures = [get_random_measure(measures_dfs).to_json() for _ in range(15)]


with Agent.create(
    model="composer-2.5",
    api_key=os.environ['CURSOR_API_KEY'],
    local=LocalAgentOptions(cwd=os.getcwd()),
) as agent:
    df = measures_dfs[0]
    keyname = 'inferred:location_clues' 
    df[keyname] = None
    chunk_size = 10
    for s in tqdm(range(0, df.shape[0], chunk_size)):
        sl = s, s+chunk_size-1
        chunk = df.iloc[sl[0]: sl[1] + 1]
        user_prompt = (
            "Extrahiere anhand der unten aufgelisteten Beispiele aus der Tabellenzeile Ortsbezeichnungen, die später für fuzzy string matching mit OpenStreetMap-Features benutzt werden können." 
            + "Gib einen json-serializable string zurück: list[list[str]] \n"
            + "Die äußere Liste soll genauso lang sein wie die Anzahl der Maßnahmen, die dir übergeben werden.\n"
            + f"Beispiele:\n{with_clues}\n\n"
            + f"Tabellenzeilen\n{chunk.to_json()}"
        )
        
        #result = agent.send(user_prompt).text()
        valid_json_objects = JsonExtractor.extract_valid_json(result)
        
        assert len(valid_json_objects) == chunk.shape[0]
        df.loc[sl[0]:sl[1], keyname] = [str(v) for v in valid_json_objects]
    
    result_path = OUT_DIR / Path(df.iloc[0].source_file).parent.name
    result_path.mkdir(exist_ok=True) 
    df.to_csv(result_path, ignore_index=True)
