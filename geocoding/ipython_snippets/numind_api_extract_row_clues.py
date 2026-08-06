import os
import json 
import asyncio
import re

from numind import NuMindAsync

from lib.measures import collect_raw_measures_dfs_from_csvs

client = NuMindAsync(api_key=os.environ.get('NUMIND_API_KEY'))
project_id = 'sprj_01ktrsfpgwcjp84rtnrq8akbdq'

with open('artefacts/01_sampled_measures_labelled.json', 'r') as f:
    sampled_measures = json.load(f)


measures = [{k: v for k, v in m.items() if not 'label' in k} for m in sampled_measures if 'label:location_clues' in m.keys()]
labels = [{'location_clues': m['label:location_clues'], 'asset_type': m['label:asset_type']} for m in sampled_measures if 'label:location_clues' in m.keys()]
for i in range(len(labels)):
    if labels[i]['asset_type'] is not None and 'transformer_' in labels[i]['asset_type']:
        labels[i]['asset_type'] = 'substation'
examples = [(json.dumps(m, ensure_ascii=False), l) for m, l in zip(measures, labels, strict=True)]
template = {
    "location_clues": [
        "string"
    ],
    "asset_type": [
        "power_line",
        "substation",
        "generator"
    ]
}
instructions = """
The examples show exemplary location_clues under the key 'label:location_clues' and exemplary asset_types under 'label:asset_type'.
For location clues, only extract names of streets, municipalities, areas, districts, or regions. No domain-specific abbreviations such as UW, GmbH or HKW.
"""

measures_dfs = collect_raw_measures_dfs_from_csvs('../pdfplumber_table_extraction/')
df = measures_dfs[1]

requests = [{'template': template, 'examples': examples, 'instructions': instructions, 'input_text': df.iloc[i].to_json()} for i in range(10,15)]

async def main():
    return [
        await client.extract_structured_data(**request_kwargs)
        for request_kwargs in requests
    ]

responses = asyncio.run(main())
