import json
from typing import Tuple, Hashable, Mapping

import pandas as pd
import geopandas as gpd
from pyrosm import OSM
from rapidfuzz import process, fuzz


def fuzzy_match_substations(transformer_station_name: str, substations: pd.DataFrame) -> list[Tuple[str, float, Hashable]]:
    choices_by_index: Mapping[Hashable, str] = substations["tag::name"].dropna().to_dict()

    return process.extract(
        query=transformer_station_name,
        choices=choices_by_index,
        scorer=fuzz.WRatio,
        score_cutoff=75,
        limit=10,
    )

def get_all_substations(osm_reader: OSM) -> gpd.GeoDataFrame | None:
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
