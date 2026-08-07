import json
from enum import Enum
from tqdm import tqdm
from pathlib import Path

from pydantic import BaseModel, ValidationError
from ollama import chat
import pandas as pd

from lib.measures import collect_raw_measures_dfs_from_csvs 


class SystemPrompt:
    def __init__(self, instructions: str, rules: str, schema: dict, examples_string: str) -> None:
        self.instructions = instructions
        self.rules = rules
        self.schema = schema
        self.examples_string = examples_string
        
    def __str__(self) -> str:
        return f"""
            Instructions:
            {self.instructions}
            
            Rules:
            {self.rules}
            
            JSON schema:
            {json.dumps(self.schema, ensure_ascii=False)}
            
            Examples:
            {self.examples_string}
            
            """
            
if not 'all_requests' in globals():
    all_requests: list = []

class AssetType(str, Enum):
    power_line: str = 'power_line'
    substation: str = 'substation'
    generator: str = 'generator'

class ExtractionResult(BaseModel):
    location_clues: list[str]
    asset_type: AssetType | None

if __name__ = '__main__':
    
    OUT_DIR = Path('./artefacts')
    in_paths = Path('../table_extraction/output').rglob('**/*csv')
    
    for p in in_paths:
        with open('artefacts/01_sampled_measures_labelled.json', 'r') as f:
            sampled_measures = json.load(f)
            
        measures = [{k: v for k, v in m.items() if not 'label' in k} for m in sampled_measures if 'label:location_clues' in m.keys()]
        labels = [{'location_clues': m['label:location_clues'], 'asset_type': m['label:asset_type']} for m in sampled_measures if 'label:location_clues' in m.keys()]
        for i in range(len(labels)):
            if labels[i]['asset_type'] is not None and 'transformer_' in labels[i]['asset_type']:
                labels[i]['asset_type'] = 'substation'
        examples = [(json.dumps(m, ensure_ascii=False), l) for m, l in zip(measures, labels, strict=True)]
        examples_string = '\n\n\n'.join([e[0].replace('nan', 'null') + '\n ------------->\n' + str(e[1]) for e in examples])
        
        out_path = OUT_DIR / p.parent.name / p.name
        
        if out_path.exists():
            df = pd.read_csv(out_path)
            df_result = df.copy()
        else:
            df = pd.read_csv(p)
            df_result = df.copy()
            df_result['inferred:location_clues'] = None
            df_result['inferred:asset_type'] = None
            
        
        row_indices = df.index[(df['inferred:location_clues'].isna() & df['inferred:asset_type'].isna())].tolist()
        
        for row_idx in tqdm(row_indices):#df.shape[0])):    
            row = df.iloc[row_idx].to_dict()
            
            schema: dict = ExtractionResult.model_json_schema()
            instructions = """
            Extract location clues and asset type from the row.
            
            For location clues, only extract names of streets, municipalities, areas, districts, or regions. No domain-specific abbreviations such as UW, GmbH or HKW.
            """
            rules = """
            
                    - Return ONLY JSON.
                    - No markdown.
                    - No explanation.
                    - location_clues must be a list of strings.
                    - asset_type must be one of: power_line, substation, generator, null.
                    - If unclear, use null.
            """ 
            system_prompt = SystemPrompt(instructions=instructions, schema=schema, rules=rules, examples_string=examples_string) 
            request = {
                'model': "nuextract3-gguf",
                'messages': [
                    {"role": "system", "content": str(system_prompt)},
                    {"role": "user", "content": str(row)}], 
                'format': schema,
                'options': {
                    "temperature": 0,
                    "num_ctx": int(2**14),
                    "num_predict": 512,
                },
                "think": False 
            }
            response = chat(
               **request
            )
            all_requests.append((request, response))
            
            prediction_dict = json.loads(response.message.content)
            df_result.loc[row_idx, 'inferred:location_clues'] = str(prediction_dict['location_clues'])
            df_result.loc[row_idx, 'inferred:asset_type'] = prediction_dict['asset_type']
            
            out_path.parent.mkdir(exist_ok=True)
            df_result.to_csv(out_path, index=False)
