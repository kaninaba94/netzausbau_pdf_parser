import json
from enum import Enum
from tqdm import tqdm

from pydantic import BaseModel, ValidationError
from ollama import chat

from lib.measures import collect_raw_measures_dfs_from_csvs 

class AssetType(str, Enum):
    power_line: str = 'power_line'
    substation: str = 'substation'
    generator: str = 'generator'

class ExtractionResult(BaseModel):
    location_clues: list[str]
    asset_type: AssetType | None

def _jsonable(d: dict) -> str:
    return str(d).replace('\'', '\"')


with open('artefacts/01_sampled_measures_labelled.json', 'r') as f:
    sampled_measures = json.load(f)
    
measures = [{k: v for k, v in m.items() if not 'label' in k} for m in sampled_measures if 'label:location_clues' in m.keys()]
labels = [{'location_clues': m['label:location_clues'], 'asset_type': m['label:asset_type']} for m in sampled_measures if 'label:location_clues' in m.keys()]
for i in range(len(labels)):
    if labels[i]['asset_type'] is not None and 'transformer_' in labels[i]['asset_type']:
        labels[i]['asset_type'] = 'substation'
examples = [(_jsonable(m), l) for m, l in zip(measures, labels, strict=True)]
examples_string = '\n\n\n'.join([e[0].replace('nan', 'null') + '\n ------------->\n' + str(e[1]) for e in examples])

measures_dfs = collect_raw_measures_dfs_from_csvs('../pdfplumber_table_extraction/')
df = measures_dfs[1]

for row_idx in tqdm(range(5)):    
    row = df.iloc[row_idx].to_dict()
    
    schema = ExtractionResult.model_json_schema()
    instructions = """
    The examples show exemplary location_clues under the key 'label:location_clues' and exemplary asset_types under 'label:asset_type'.
    For location clues, only extract names of streets, municipalities, areas, districts, or regions. No domain-specific abbreviations such as UW, GmbH or HKW.
    """
    
    prompt = f"""
    {instructions}
    Extract location clues and asset type from the row.
    
    Rules:
    - Return ONLY JSON.
    - No markdown.
    - No explanation.
    - location_clues must be a list of strings.
    - asset_type must be one of: power_line, substation, generator, null.
    - If unclear, use null.
    
    JSON schema:
    {json.dumps(schema, ensure_ascii=False)}
    
    Examples for in-context-learning:
    {examples_string}
    
    Input row:
    {row}
    """
    request = {
        'model': "nuextract3-gguf",
        'messages': [{"role": "user", "content": prompt}], 
        'format': schema,
        'options': {
            "temperature": 0,
            "num_ctx": int(2**14),
            "num_predict": 512,
        },
    }
    response = chat(
        **request
    )
    all_requests.append((request, response))
