import json 
from typing import Union
from pathlib import Path

SCHEMA_PATH = 'netzausbau_extractor/schemas/v1.json' 

def load_extraction_schema(json_path: Union[str, Path]) -> dict:
    with open(json_path, 'r') as f:
        schema = json.load(f)
    return schema

