import json
from typing import Tuple, Hashable, Mapping

import pandas as pd
import geopandas as gpd
from pyrosm import OSM
from rapidfuzz import process, fuzz


def fuzzy_match_substations(transformer_station_name: str, substations: gpd.GeoDataFrame) -> list[Tuple[str, float, Hashable]]:
    choices_by_index: Mapping[Hashable, str] = substations["tag::name"].dropna().to_dict()

    return process.extract(
        query=transformer_station_name,
        choices=choices_by_index,
        scorer=fuzz.WRatio,
        score_cutoff=75,
        limit=10,
    )

def get_all_substations(osm_reader: OSM, expand_tags: bool = True) -> gpd.GeoDataFrame | None:
    substations: gpd.GeoDataFrame | None = osm_reader.get_data_by_custom_criteria(
        custom_filter={"power": ["substation"]},
        filter_type="keep",
        keep_nodes=False,
        keep_ways=True,
        keep_relations=False,
    );
    if expand_tags is True and substations is not None:
        tags_df = pd.DataFrame(
            [json.loads(tags) for tags in substations["tags"]],
            index=substations.index,
            ).add_prefix('tag::')
    
        substations = substations.drop(columns="tags").join(tags_df)
    return substations


def serialize_substation(substation: pd.Series, field_names: list[str]) -> str:
    serialized_fields: list[str] = []

    for field_name in field_names:
        value = substation.get(field_name)
        if value is None or pd.isna(value):
            continue
        serialized_fields.append(f"{field_name}: {value}")
     
    return "passage: " + "; ".join(serialized_fields)



def search_by_osm_id(osm_id: int, substations_df: pd.DataFrame) -> pd.Series:
    substation = substations_df.loc[substations_df['id'] == int(osm_id)]
    assert substation.shape[0] == 1
    return substation.iloc[0]
