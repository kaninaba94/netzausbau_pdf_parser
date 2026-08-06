from pathlib import Path

import json
import re
column_id_per_file = dict()
wd = Path()
regex_pattern = re.compile('.*betrieb.*', re.IGNORECASE)
for p in (wd/'output').rglob('**json'):
    print('=====', p)
    with open(p, 'r') as f:
        measures = json.load(f)        
        for i, t in enumerate(measures[0]):
            if regex_pattern.match(t):
                assert p not in column_id_per_file
                column_id_per_file[p] = i

unique_values = set()
for fp, col_num in column_id_per_file.items():
    with open(fp, 'r') as f:
        measures = json.load(f)
                
        unique_values = unique_values.union(set([m[col_num].strip(' ').replace('\n', '') for m in measures[1:]]))

unique_values_iter = iter(sorted(unique_values))
