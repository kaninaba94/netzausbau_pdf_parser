from pathlib import Path
import ast

import pandas as pd
from pyrosm import OSM

from lib.osm import get_all_substations, fuzzy_match_substations


if __name__ == '__main__':
    in_paths = Path('artefacts/row_clues').rglob('**/*csv')
    for p in in_paths:
        out_path = Path('artefacts') / 'geocoded' / p.parent.name / f"{p.stem}.csv"
        out_path.parent.mkdir(exist_ok=True)
        
        if not 'substations_df' in globals():
            pbf_path = Path("../data/osm/germany-power.osm.pbf")
            osm_reader = OSM(
                filepath=str(pbf_path),
                bounding_box=None,
            )
            substations_df = get_all_substations(osm_reader)
            
        in_df = pd.read_csv(p)
        out_df = in_df.copy()
        if 'inferred:osm_id' not in out_df.columns:
            out_df['inferred:osm_id'] = None
        row_indices = out_df.index[out_df['inferred:osm_id'].isna()].tolist()
            
        for row_idx in row_indices:
            row = out_df.iloc[row_idx]
            location_clues: list[str] = ast.literal_eval(row['inferred:location_clues'])
            asset_type: str = row['inferred:asset_type']
            if not asset_type == 'substation':
                continue
            substation_name = location_clues[0]
            matches = fuzzy_match_substations(substation_name, substations_df) 
            matched_substations_df = substations_df.loc[[match[2] for match in matches]]
            out_df.loc[row_idx, 'inferred:osm_id'] = matched_substations_df.iloc[0]['id']
            out_df.to_csv(out_path)
            print(f"https://www.openstreetmap.org/way/{matched_substations_df.iloc[0]['id']}") 
            print(substation_name, '\n', matched_substations_df, '\n')
        
