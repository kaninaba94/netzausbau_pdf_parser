from pathlib import Path
import re 
import json
from pprint import pprint

import geopandas as gpd
from pyrosm import OSM



def get_all_substations(osm_reader: OSM) -> pd.DataFrame:
    substations: gpd.GeoDataFrame | None = osm_reader.get_data_by_custom_criteria(
        custom_filter={"power": ["substation"]},
        filter_type="keep",
        keep_nodes=False,
        keep_ways=True,
        keep_relations=False,
    );
    if substations is not None:
        tags_df = pd.DataFrame(
            [json.loads(tags) for tags in substations["tags"]],
            index=substations.index,
            ).add_prefix('tag::')
    
        substations = substations.drop(columns="tags").join(tags_df)
    return substations



if __name__ '__main__':
    pbf_path = Path("../data/osm/germany-power.osm.pbf")
    
    osm_reader = OSM(
        filepath=str(pbf_path),
        bounding_box=None,
    )

