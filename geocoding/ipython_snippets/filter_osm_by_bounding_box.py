from pathlib import Path

import geopandas as gpd
from pyrosm import OSM

pbf_path = Path("../data/osm/germany-power.osm.pbf")

# [min_lon, min_lat, max_lon, max_lat]
bounding_box = [8.0, 52.4, 8.5, 52.8]

osm_reader = OSM(
    filepath=str(pbf_path),
    bounding_box=bounding_box,
)

substations: gpd.GeoDataFrame | None = osm_reader.get_data_by_custom_criteria(
    custom_filter={"power": ["substation"]},
    filter_type="keep",
    keep_nodes=True,
    keep_ways=True,
    keep_relations=True,
)
