from pathlib import Path

from pyrosm import OSM

from lib.osm import get_all_substations


if __name__ == '__main__':
    pbf_path = Path("../data/osm/germany-power.osm.pbf")
    
    osm_reader = OSM(
        filepath=str(pbf_path),
        bounding_box=None,
    )
    substations = get_all_substations(osm_reader)

